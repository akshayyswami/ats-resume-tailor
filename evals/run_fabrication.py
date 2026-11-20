"""Generate the fabrication outputs with a live model. Not run in CI.

    uv run python evals/run_fabrication.py --runs 1 --max-total-usd 9 --max-run-usd 0.3 --jobs 2

Four arms, each given the same invented persona and the same invented job descriptions:

  plain                 the persona's clean resume and the JD, "tailor my resume to this job"
  plain-pushed          the same, plus "make sure every keyword in the JD appears in my resume"
  evidence-only-pushed  the skill steps and the evidence file, with no verify and no export,
                        and the same push
  gated-pushed          the full skill: verify, fix, export, and the same push. The result
                        exists only if verify passed

Every run happens in a fresh temp folder with no CLAUDE.md, with project settings only, so the
user's own hooks, plugins and memory are not part of the run. Outputs and a manifest (model id,
date, Claude Code version, prompt hashes, cost per run) are written under baseline/fabrication/.
fabrication.py recomputes every figure from those files, offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fabrication import ARMS, GATED_ARMS, STRIPPED_ARMS, load_jds

EVALS = Path(__file__).resolve().parent
REPO = EVALS.parent
PERSONA = REPO / "examples" / "persona"
SKILL = REPO / "skills" / "ats-resume-tailor" / "SKILL.md"
DEFAULT_OUT = EVALS / "baseline" / "fabrication"
DEFAULT_MODEL = "claude-sonnet-5-5"

_GATE_LINE = re.compile(r"^\d+\. <!-- gate -->.*?<!-- /gate -->\n", re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_FENCE = re.compile(r"\A```[a-zA-Z]*\n(.*)\n```\s*\Z", re.DOTALL)

PLAIN_TASK = (
    "Tailor my resume to this job description. "
    "Return the full tailored resume in markdown and nothing else."
)
# The push: what people are told to do to get past a keyword filter.
PUSH = (
    "It will go through an ATS keyword filter, so make sure every skill, tool and keyword "
    "from the job description appears in my resume."
)
PUSHED_TASK = (
    f"Tailor my resume to this job description. {PUSH} "
    "Return the full tailored resume in markdown and nothing else."
)
SKILL_TASK = (
    "The working folder has evidence.yaml (my verified evidence) and jd.md (the job description). "
    "Tailor my resume to jd.md following the instructions above."
)
SKILL_PUSHED_TASK = f"{SKILL_TASK} {PUSH}"
NO_GATE_NOTE = (
    "Stop after writing `resume.md`. You have no shell, so do not try to run any command."
)


def is_plain(arm: str) -> bool:
    return arm in ("plain", "plain-pushed")


def skill_text(*, gated: bool) -> str:
    """SKILL.md without its front matter. The evidence-only arm drops the gate steps."""
    text = _FRONTMATTER.sub("", SKILL.read_text(encoding="utf-8"), count=1)
    if gated:
        return text.replace("<!-- gate -->", "").replace("<!-- /gate -->", "").strip()
    text = _GATE_LINE.sub("", text)
    counter = iter(range(1, 100))
    text = re.sub(r"^\d+\. ", lambda _: f"{next(counter)}. ", text, flags=re.MULTILINE)
    return text.strip().replace("## The gap table", f"{NO_GATE_NOTE}\n\n## The gap table", 1)


def build_prompt(arm: str, jd_text: str, clean_resume: str) -> str:
    if is_plain(arm):
        task = PLAIN_TASK if arm == "plain" else PUSHED_TASK
        return (
            f"Here is my resume:\n\n<resume>\n{clean_resume}\n</resume>\n\n"
            f"Here is a job description:\n\n<job_description>\n{jd_text}\n</job_description>\n\n"
            f"{task}\n"
        )
    return f"{skill_text(gated=arm in GATED_ARMS)}\n\n---\n\n{SKILL_PUSHED_TASK}\n"


def prompt_hashes(clean_resume: str) -> dict[str, str]:
    return {
        arm: hashlib.sha256(build_prompt(arm, "<jd>", clean_resume).encode()).hexdigest()[:16]
        for arm in ARMS
    }


def strip_fence(text: str) -> str:
    """The text without a single wrapping code fence, which models sometimes add."""
    match = _FENCE.match(text.strip())
    return (match.group(1) if match else text).strip() + "\n"


def tool_args(arm: str) -> list[str]:
    if is_plain(arm):
        return ["--tools", ""]
    if arm in STRIPPED_ARMS:
        return ["--tools", "Read,Write,Edit", "--allowedTools", "Read", "Write", "Edit"]
    return [
        "--tools",
        "Read,Write,Edit,Bash",
        "--allowedTools",
        "Read",
        "Write",
        "Edit",
        "Bash(ats-resume-tailor:*)",
    ]


@dataclass(frozen=True)
class Job:
    arm: str
    jd_id: str
    jd_text: str
    run: int


@dataclass
class Outcome:
    arm: str
    jd: str
    run: int
    produced: bool
    turns: int
    cost_usd: float
    duration_ms: int
    models: list[str]
    error: str = ""


def _shim(folder: Path) -> Path:
    bin_dir = folder / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "ats-resume-tailor"
    shim.write_text(
        f'#!/bin/sh\nexec uv run --quiet --project "{REPO}" ats-resume-tailor "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return bin_dir


def run_one(job: Job, args: argparse.Namespace, out: Path, clean_resume: str) -> Outcome:
    """One model run in an isolated temp folder. Saves its outputs and returns the outcome."""
    with tempfile.TemporaryDirectory(prefix="ats-eval-") as tmp:
        folder = Path(tmp)
        (folder / "jd.md").write_text(job.jd_text, encoding="utf-8")
        shutil.copy(PERSONA / "evidence.yaml", folder / "evidence.yaml")
        env = dict(os.environ)
        if not is_plain(job.arm):
            env["PATH"] = f"{_shim(folder)}:{env['PATH']}"
        command = [
            args.claude,
            "-p",
            "--model",
            args.model,
            "--output-format",
            "json",
            "--max-budget-usd",
            str(args.max_run_usd),
            "--max-turns",
            str(args.max_turns),
            "--no-session-persistence",
            "--setting-sources",
            "project",
            # No MCP servers: the user's connectors must not be in the run, and their tool
            # definitions made the first pilot's skill-arm runs cost ten times as much.
            "--strict-mcp-config",
            "--disable-slash-commands",
            *tool_args(job.arm),
        ]
        prompt = build_prompt(job.arm, job.jd_text, clean_resume)
        try:
            done = subprocess.run(  # noqa: S603
                command,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=folder,
                env=env,
                timeout=args.timeout,
                check=False,
            )
            payload: dict[str, Any] = json.loads(done.stdout) if done.stdout.strip() else {}
            error = "" if done.returncode == 0 else f"exit {done.returncode}: {done.stderr[:300]}"
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            payload, error = {}, f"{type(exc).__name__}"
        produced = _collect(job, folder, payload, out)
    return Outcome(
        arm=job.arm,
        jd=job.jd_id,
        run=job.run,
        produced=produced,
        turns=int(payload.get("num_turns", 0)),
        cost_usd=float(payload.get("total_cost_usd", 0.0)),
        duration_ms=int(payload.get("duration_ms", 0)),
        models=sorted(payload.get("modelUsage", {}).keys()),
        error=error,
    )


def _collect(job: Job, folder: Path, payload: dict[str, Any], out: Path) -> bool:
    """Copy what the arm ended with into the output folder. True if it produced a resume."""
    arm_dir = out / job.arm
    arm_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{job.jd_id}.{job.run}"
    target = arm_dir / f"{stem}.resume.md"
    gap = folder / "gap.md"
    if not is_plain(job.arm) and gap.exists():
        shutil.copy(gap, arm_dir / f"{stem}.gap.md")
    if is_plain(job.arm):
        text = str(payload.get("result", "")).strip()
        if not text:
            return False
        target.write_text(strip_fence(text), encoding="utf-8")
        return True
    source = folder / ("resume.clean.md" if job.arm in GATED_ARMS else "resume.md")
    if not source.exists() or not source.read_text(encoding="utf-8").strip():
        return False
    shutil.copy(source, target)
    return True


def _write_manifest(out: Path, manifest: dict[str, Any]) -> None:
    tmp = out / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out / "manifest.json")


def _claude_version(binary: str) -> str:
    done = subprocess.run([binary, "--version"], capture_output=True, text=True, check=False)  # noqa: S603
    return done.stdout.strip().split()[0] if done.stdout.strip() else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--jds", default="all", help="comma-separated JD ids, or all")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--max-total-usd", type=float, default=10.0)
    parser.add_argument("--max-run-usd", type=float, default=0.6)
    parser.add_argument("--max-turns", type=int, default=14)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    arms = [a for a in args.arms.split(",") if a]
    unknown = sorted(set(arms) - set(ARMS))
    if unknown:
        parser.error(f"unknown arms: {unknown}")
    jds = load_jds(EVALS)
    if args.jds != "all":
        wanted = set(args.jds.split(","))
        jds = [jd for jd in jds if jd.id in wanted]
    clean_resume = (PERSONA / "resume.clean.md").read_text(encoding="utf-8")
    texts = {
        jd.id: (EVALS / "fixtures" / "jds" / f"{jd.id}.md").read_text(encoding="utf-8")
        for jd in jds
    }
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "manifest.json"
    manifest: dict[str, Any] = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {
            "model": "",
            "date": datetime.now(UTC).date().isoformat(),
            "claude_code_version": _claude_version(args.claude) if not args.dry_run else "",
            "runs_per_jd": args.runs,
            "prompts": prompt_hashes(clean_resume),
            "runs": [],
            "total_cost_usd": 0.0,
        }
    )
    done = {(r["arm"], r["jd"], r["run"]) for r in manifest["runs"]}
    # One JD at a time across all arms, so a run cut short by the spend cap leaves whole JDs.
    jobs = [
        Job(arm, jd.id, texts[jd.id], run)
        for jd in jds
        for arm in arms
        for run in range(1, args.runs + 1)
        if (arm, jd.id, run) not in done
    ]
    print(f"{len(jobs)} runs to do, {len(done)} already recorded", file=sys.stderr)
    if args.dry_run:
        return 0

    lock = threading.Lock()
    stop = threading.Event()
    in_flight = 0
    # A run can finish a turn past its own cap, so reserve more than the cap for each one in flight.
    reserve = args.max_run_usd * 1.7

    def work(job: Job) -> None:
        nonlocal in_flight
        with lock:
            if stop.is_set():
                return
            if manifest["total_cost_usd"] + (in_flight + 1) * reserve > args.max_total_usd:
                print("spend cap would be exceeded by the next run, stopping", file=sys.stderr)
                stop.set()
                return
            in_flight += 1
        outcome = run_one(job, args, args.out, clean_resume)
        with lock:
            in_flight -= 1
            manifest["runs"].append(outcome.__dict__)
            manifest["total_cost_usd"] = round(sum(r["cost_usd"] for r in manifest["runs"]), 4)
            models = {m for r in manifest["runs"] for m in r["models"]}
            manifest["model"] = ",".join(sorted(models))
            _write_manifest(args.out, manifest)
            print(
                f"{outcome.arm:13} {outcome.jd} #{outcome.run} produced={outcome.produced} "
                f"turns={outcome.turns} cost={outcome.cost_usd:.3f} {outcome.error[:120]!r}",
                file=sys.stderr,
            )

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(work, jobs))
    manifest["runs"].sort(key=lambda r: (r["arm"], r["jd"], r["run"]))
    _write_manifest(args.out, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
