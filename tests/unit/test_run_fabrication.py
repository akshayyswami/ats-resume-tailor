from __future__ import annotations

import json
import re
import stat
from pathlib import Path
from types import ModuleType

import pytest

from tests.unit.test_fabrication import EVALS, load_eval_module

FAKE_CLAUDE = """#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
if "--version" in args:
    print("9.9.9 (Claude Code)")
    raise SystemExit(0)
sys.stdin.read()
tools = args[args.index("--tools") + 1]
cwd = pathlib.Path.cwd()
jd = (cwd / "jd.md").read_text()
meta = {
    "num_turns": 3,
    "total_cost_usd": 0.01,
    "duration_ms": 5,
    "modelUsage": {"fake-model": {}},
}
gap = (
    "| Requirement | Status | Terms | Evidence |\\n|---|---|---|---|\\n"
    "| x | HAVE | python | E001 |\\n"
)
if tools == "":
    body = "# Jordan Lee\\n\\n- Wrote Terraform modules.\\n"
    print(json.dumps({"result": "```markdown\\n" + body + "```", **meta}))
elif "Bash" in tools:
    (cwd / "gap.md").write_text(gap)
    if "Senior" not in jd:
        (cwd / "resume.clean.md").write_text("# Jordan Lee\\n\\n- Built a thing.\\n")
    print(json.dumps({"result": "done", **meta}))
else:
    (cwd / "gap.md").write_text(gap)
    resume = "# Jordan Lee\\n\\n## Experience\\n\\n- Built a thing. [E001]\\n"
    (cwd / "resume.md").write_text(resume)
    print(json.dumps({"result": "done", **meta}))
"""


@pytest.fixture
def run() -> ModuleType:
    load_eval_module("fabrication")
    return load_eval_module("run_fabrication")


@pytest.fixture
def fake_claude(tmp_path: Path) -> str:
    path = tmp_path / "claude"
    path.write_text(FAKE_CLAUDE, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def numbers(text: str) -> list[int]:
    return [int(m.group(1)) for m in re.finditer(r"^(\d+)\. ", text, re.MULTILINE)]


def test_the_gated_skill_keeps_every_step_and_drops_the_markers(run: ModuleType) -> None:
    text = run.skill_text(gated=True)
    assert "<!--" not in text
    assert "ats-resume-tailor verify resume.md" in text
    assert "ats-resume-tailor export" in text
    assert numbers(text) == list(range(1, 9))


def test_the_evidence_only_skill_drops_the_gate_and_renumbers(run: ModuleType) -> None:
    text = run.skill_text(gated=False)
    assert "<!--" not in text
    assert "ats-resume-tailor verify" not in text
    assert "ats-resume-tailor export" not in text
    assert "check-evidence" not in text
    assert numbers(text) == [1, 2, 3, 4]
    assert "You have no shell" in text
    assert "Never edit `evidence.yaml`" not in text.split("## The gap table")[0]


def test_each_arm_gets_its_own_prompt_and_tools(run: ModuleType) -> None:
    prompts = {arm: run.build_prompt(arm, "JD TEXT", "RESUME TEXT") for arm in run.ARMS}
    assert "RESUME TEXT" in prompts["plain"]
    assert "ATS keyword filter" in prompts["plain-pushed"]
    assert "ATS keyword filter" not in prompts["plain"]
    assert "RESUME TEXT" not in prompts["gated-pushed"]  # the skill arms start from the evidence
    assert len(set(prompts.values())) == 4
    assert run.tool_args("plain") == ["--tools", ""]
    assert "Bash" not in " ".join(run.tool_args("evidence-only-pushed"))
    assert "Bash(ats-resume-tailor:*)" in run.tool_args("gated-pushed")
    assert set(run.prompt_hashes("RESUME")) == set(run.ARMS)


def test_strip_fence_removes_one_wrapping_fence_only(run: ModuleType) -> None:
    assert run.strip_fence("```markdown\n# A\n\n- b\n```") == "# A\n\n- b\n"
    assert run.strip_fence("# A\n\n```\ncode\n```\n") == "# A\n\n```\ncode\n```\n"


def test_a_full_pass_with_a_fake_model(run: ModuleType, fake_claude: str, tmp_path: Path) -> None:
    out = tmp_path / "out"
    argv = ["--claude", fake_claude, "--out", str(out), "--jds", "jd-01,jd-02", "--runs", "1"]
    assert run.main([*argv, "--jobs", "1"]) == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["model"] == "fake-model"
    assert manifest["claude_code_version"] == "9.9.9"
    assert manifest["runs_per_jd"] == 1
    assert len(manifest["runs"]) == 8
    assert manifest["total_cost_usd"] == 0.08
    assert set(manifest["prompts"]) == set(run.ARMS)
    produced = {(r["arm"], r["jd"]): r["produced"] for r in manifest["runs"]}
    assert produced[("gated-pushed", "jd-01")] is True
    assert produced[("gated-pushed", "jd-02")] is False  # the fake never exports for a Senior JD
    assert not (out / "gated-pushed" / "jd-02.1.resume.md").exists()
    assert (out / "gated-pushed" / "jd-02.1.gap.md").exists()
    plain = (out / "plain" / "jd-01.1.resume.md").read_text(encoding="utf-8")
    assert plain == "# Jordan Lee\n\n- Wrote Terraform modules.\n"
    annotated = (out / "evidence-only-pushed" / "jd-01.1.resume.md").read_text(encoding="utf-8")
    assert "[E001]" in annotated
    # A second pass records nothing new.
    assert run.main([*argv, "--jobs", "1"]) == 0
    again = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(again["runs"]) == 8


def test_the_spend_cap_stops_the_run(run: ModuleType, fake_claude: str, tmp_path: Path) -> None:
    out = tmp_path / "out"
    argv = [
        "--claude", fake_claude, "--out", str(out), "--jds", "jd-01", "--runs", "2",
        "--jobs", "1", "--max-total-usd", "0.02", "--max-run-usd", "0.005",
    ]  # fmt: skip
    assert run.main(argv) == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["runs"]) == 2


def test_the_spend_cap_counts_runs_still_in_flight(
    run: ModuleType, fake_claude: str, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    # Four workers, 1.02 reserved each: a 1.5 cap allows one run to start, whatever it costs later.
    argv = ["--claude", fake_claude, "--out", str(out), "--jds", "jd-01", "--runs", "2"]
    assert run.main([*argv, "--jobs", "4", "--max-total-usd", "1.5"]) == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert 1 <= len(manifest["runs"]) < 8


def test_a_run_cut_short_by_the_cap_leaves_whole_jds(
    run: ModuleType, fake_claude: str, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    argv = ["--claude", fake_claude, "--out", str(out), "--jds", "jd-01,jd-02", "--runs", "1"]
    argv += ["--jobs", "1", "--max-total-usd", "0.055", "--max-run-usd", "0.01"]
    assert run.main(argv) == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert {r["jd"] for r in manifest["runs"]} == {"jd-01"}
    assert {r["arm"] for r in manifest["runs"]} == set(run.ARMS)


def test_every_run_excludes_mcp_servers(run: ModuleType, fake_claude: str, tmp_path: Path) -> None:
    seen = tmp_path / "args.txt"
    script = Path(fake_claude)
    script.write_text(
        script.read_text(encoding="utf-8").replace(
            "args = sys.argv[1:]\n",
            f"args = sys.argv[1:]\nopen({str(seen)!r}, 'a').write(' '.join(args) + chr(10))\n",
            1,
        ),
        encoding="utf-8",
    )
    argv = ["--claude", fake_claude, "--out", str(tmp_path / "o"), "--jds", "jd-01", "--runs", "1"]
    argv += ["--arms", "plain,gated-pushed", "--jobs", "1"]
    assert run.main(argv) == 0
    lines = [line for line in seen.read_text(encoding="utf-8").splitlines() if "--model" in line]
    assert len(lines) == 2
    assert all(
        "--strict-mcp-config" in line and "--setting-sources project" in line for line in lines
    )


def test_dry_run_writes_nothing_and_unknown_arms_are_refused(
    run: ModuleType, fake_claude: str, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    assert run.main(["--claude", fake_claude, "--out", str(out), "--dry-run"]) == 0
    assert not (out / "manifest.json").exists()
    with pytest.raises(SystemExit):
        run.main(["--arms", "nope", "--out", str(out)])


def test_the_runner_reads_the_real_skill() -> None:
    assert (EVALS.parent / "skills" / "ats-resume-tailor" / "SKILL.md").exists()
