"""Trigger test for the skill description. Calls a live model, so it is not run in CI.

    uv run python evals/run_trigger.py --runs 3

Reads the cases in skill-evals/, which use the format `claude plugin eval` reads, and runs each
request through `claude -p` in a clean session: project settings only, no MCP servers, and this
plugin as the only source of skills. A case passes when the skill is, or is not, invoked as its
grader says. The result goes to skill-evals/last-run.json, with the model, the date and the
skills the session could see, so a reader can tell the run was not crowded by other skills.

Why not `claude plugin eval`: it runs as the logged-in user and loads their own plugins and MCP
servers, which made one run cost about 0.23 USD and put the skill among dozens of others. This
runner costs a few cents a run and tests the description on its own. The cases still work with
`claude plugin eval` for anyone who wants their own environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "skill-evals"
PERSONA = REPO / "examples" / "persona"
DEFAULT_MODEL = "claude-sonnet-5-5"
TOOLS = ("Skill", "Read", "Glob", "Grep")
_FRONT = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class Grader:
    tool: str
    input_match: str | None
    minimum: int
    maximum: int | None


@dataclass(frozen=True)
class Case:
    name: str
    prompt: str
    graders: tuple[Grader, ...]

    @property
    def expects_skill(self) -> bool:
        return any(g.minimum >= 1 for g in self.graders)


@dataclass
class Outcome:
    case: str
    run: int
    passed: bool
    skill_inputs: list[str]
    turns: int
    cost_usd: float
    error: str = ""


def _split(text: str) -> tuple[dict[str, Any], str]:
    match = _FRONT.match(text)
    if match is None:
        return {}, text.strip()
    meta = yaml.safe_load(match.group(1)) or {}
    return (meta if isinstance(meta, dict) else {}), match.group(2).strip()


def load_cases(root: Path) -> list[Case]:
    """Every folder with a prompt.md and tool_used graders, in name order."""
    cases: list[Case] = []
    for folder in sorted(p for p in root.iterdir() if (p / "prompt.md").is_file()):
        _, prompt = _split((folder / "prompt.md").read_text(encoding="utf-8"))
        graders: list[Grader] = []
        for path in sorted((folder / "graders").glob("*.md")):
            meta, _ = _split(path.read_text(encoding="utf-8"))
            if meta.get("type") != "tool_used":
                continue
            maximum = meta.get("max")
            graders.append(
                Grader(
                    tool=str(meta["tool"]),
                    input_match=meta.get("input_match"),
                    minimum=int(meta.get("min", 1)),
                    maximum=None if maximum is None else int(maximum),
                )
            )
        if not graders:
            raise ValueError(f"{folder.name} has no tool_used grader")
        cases.append(Case(folder.name, prompt, tuple(graders)))
    return cases


def events(stream: str) -> list[dict[str, Any]]:
    """The JSON objects in a stream-json transcript. Lines that are not JSON are skipped."""
    found: list[dict[str, Any]] = []
    for line in stream.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            found.append(item)
    return found


def tool_calls(items: list[dict[str, Any]], tool: str) -> list[str]:
    """The inputs, as JSON text, of every call to `tool` in the transcript."""
    calls: list[str] = []
    for item in items:
        message = item.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if item.get("type") != "assistant" or not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == tool
            ):
                calls.append(json.dumps(block.get("input", {}), sort_keys=True))
    return calls


def visible_skills(items: list[dict[str, Any]]) -> list[str]:
    """The skill names the session announced in its init event."""
    for item in items:
        if item.get("type") == "system" and item.get("subtype") == "init":
            skills = item.get("skills")
            return sorted(str(s) for s in skills) if isinstance(skills, list) else []
    return []


def grade(grader: Grader, items: list[dict[str, Any]]) -> bool:
    calls = tool_calls(items, grader.tool)
    if grader.input_match is not None:
        calls = [c for c in calls if re.search(grader.input_match, c)]
    count = len(calls)
    return count >= grader.minimum and (grader.maximum is None or count <= grader.maximum)


def run_one(case: Case, run: int, args: argparse.Namespace) -> tuple[Outcome, list[str]]:
    """One request in a fresh folder holding the persona's evidence and resume."""
    with tempfile.TemporaryDirectory(prefix="ats-trigger-") as tmp:
        folder = Path(tmp)
        shutil.copy(PERSONA / "evidence.yaml", folder / "evidence.yaml")
        shutil.copy(PERSONA / "resume.md", folder / "resume.md")
        command = [
            args.claude,
            "-p",
            "--model",
            args.model,
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-budget-usd",
            str(args.max_run_usd),
            "--max-turns",
            str(args.max_turns),
            "--no-session-persistence",
            "--setting-sources",
            "project",
            "--strict-mcp-config",
            "--plugin-dir",
            str(REPO),
            "--tools",
            ",".join(TOOLS),
            "--allowedTools",
            *TOOLS,
        ]
        error = ""
        try:
            done = subprocess.run(  # noqa: S603
                command,
                input=case.prompt,
                capture_output=True,
                text=True,
                cwd=folder,
                timeout=args.timeout,
                check=False,
            )
            stream = done.stdout
        except subprocess.TimeoutExpired:
            stream, error = "", "timeout"
    items = events(stream)
    result: dict[str, Any] = next((i for i in reversed(items) if i.get("type") == "result"), {})
    # Hitting the turn limit is expected: the grader only needs the first tool call.
    if result.get("is_error") and not error and result.get("subtype") != "error_max_turns":
        error = str(result.get("subtype") or result.get("result") or "error")[:120]
    passed = bool(items) and all(grade(g, items) for g in case.graders)
    outcome = Outcome(
        case=case.name,
        run=run,
        passed=passed,
        skill_inputs=tool_calls(items, "Skill"),
        turns=int(result.get("num_turns", 0)),
        cost_usd=float(result.get("total_cost_usd", 0.0)),
        error=error,
    )
    return outcome, visible_skills(items)


def description_hash() -> str:
    """A short hash of every description a model sees: the skill's and each command's.

    last-run.json stores it, and a test compares it, so editing a description without running
    this test again is caught.
    """
    files = [
        *sorted((REPO / "skills").glob("*/SKILL.md")),
        *sorted((REPO / "commands").glob("*.md")),
    ]
    lines = []
    for path in files:
        meta, _ = _split(path.read_text(encoding="utf-8"))
        lines.append(f"{path.relative_to(REPO)}:{meta.get('description', '')}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]


def _claude_version(binary: str) -> str:
    done = subprocess.run([binary, "--version"], capture_output=True, text=True, check=False)  # noqa: S603
    return done.stdout.split()[0] if done.stdout.split() else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-total-usd", type=float, default=1.5)
    parser.add_argument("--max-run-usd", type=float, default=0.15)
    parser.add_argument("--max-turns", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--out", type=Path, default=CASES / "last-run.json")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    outcomes: list[Outcome] = []
    seen: set[str] = set()
    spent = 0.0
    reserve = args.max_run_usd * 1.7
    stopped = False
    for case in cases:
        for run in range(1, args.runs + 1):
            if spent + reserve > args.max_total_usd:
                print("spend cap would be exceeded by the next run, stopping", file=sys.stderr)
                stopped = True
                break
            outcome, skills = run_one(case, run, args)
            spent += outcome.cost_usd
            seen.update(skills)
            outcomes.append(outcome)
            print(
                f"{case.name:32} #{run} passed={outcome.passed} cost={outcome.cost_usd:.3f} "
                f"skill={outcome.skill_inputs or '-'} {outcome.error}",
                file=sys.stderr,
            )
        if stopped:
            break

    summary: dict[str, Any] = {}
    for case in cases:
        mine = [o for o in outcomes if o.case == case.name]
        summary[case.name] = {
            "expects": "fires" if case.expects_skill else "stays quiet",
            "runs": len(mine),
            "passed": sum(o.passed for o in mine),
            "errors": sum(bool(o.error) for o in mine),
        }
    record = {
        "model": args.model,
        "date": datetime.now(UTC).date().isoformat(),
        "claude_code_version": _claude_version(args.claude),
        "descriptions_sha256": description_hash(),
        "runs_per_case": args.runs,
        "cost_usd": round(spent, 4),
        "stopped_early": stopped,
        "skills_visible_to_the_session": sorted(seen),
        "cases": summary,
        "runs": [o.__dict__ for o in outcomes],
    }
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failed = sum(1 for o in outcomes if not o.passed)
    print(f"{len(outcomes) - failed} of {len(outcomes)} runs passed, cost {spent:.3f} USD")
    return 1 if failed or stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
