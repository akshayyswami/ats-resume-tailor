from __future__ import annotations

import json
import stat
from pathlib import Path
from types import ModuleType

import pytest

from tests.unit.test_fabrication import EVALS, load_eval_module

SKILL = "ats-resume-tailor:ats-resume-tailor"

FAKE_CLAUDE = """#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
open(ARGS_FILE, "a").write(" ".join(args) + chr(10))
if "--version" in args:
    print("9.9.9 (Claude Code)")
    raise SystemExit(0)
prompt = sys.stdin.read()
cwd = pathlib.Path.cwd()
assert (cwd / "evidence.yaml").exists() and (cwd / "resume.md").exists()
print(json.dumps({"type": "system", "subtype": "init", "skills": ["SKILL"]}))
if FIRES and "evidence" in prompt.lower():
    block = {"type": "tool_use", "name": "Skill", "input": {"skill": "SKILL"}}
    print(json.dumps({"type": "assistant", "message": {"content": [block]}}))
print("this line is not json")
print(json.dumps({"type": "result", "is_error": False, "num_turns": 2, "total_cost_usd": 0.01}))
"""


@pytest.fixture
def trigger() -> ModuleType:
    load_eval_module("fabrication")
    return load_eval_module("run_trigger")


def fake(tmp_path: Path, *, fires: bool = True) -> tuple[str, Path]:
    args_file = tmp_path / "args.txt"
    body = FAKE_CLAUDE.replace("ARGS_FILE", repr(str(args_file))).replace("FIRES", str(fires))
    path = tmp_path / "claude"
    path.write_text(body.replace("SKILL", SKILL), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path), args_file


def test_the_real_cases_load_and_split_three_to_four(trigger: ModuleType) -> None:
    cases = trigger.load_cases(EVALS.parent / "skill-evals")
    assert len(cases) == 7
    fires = [c.name for c in cases if c.expects_skill]
    assert fires == [
        "fires-check-claims",
        "fires-match-without-inventing",
        "fires-tailor-with-evidence",
    ]
    assert all(c.prompt for c in cases)


def test_a_folder_with_no_tool_grader_is_an_error(trigger: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "prompt.md").write_text("---\nmax_turns: 2\n---\n\nhello\n")
    with pytest.raises(ValueError, match="no tool_used grader"):
        trigger.load_cases(tmp_path)


def test_grading_counts_matching_calls_between_min_and_max(trigger: ModuleType) -> None:
    called = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": SKILL}},
            {"type": "tool_use", "name": "Read", "input": {"file_path": "x"}},
        ]}}
    ]  # fmt: skip
    wants = trigger.Grader("Skill", r'"skill"\s*:\s*"ats-resume-tailor(?::[\w-]+)?"', 1, None)
    other = trigger.Grader("Skill", r'"skill"\s*:\s*"something-else"', 1, None)
    quiet = trigger.Grader("Skill", None, 0, 0)
    assert trigger.grade(wants, called)
    command = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "ats-resume-tailor:verify"}}
        ]}}
    ]  # fmt: skip
    assert trigger.grade(wants, command)  # a plugin command counts as the plugin firing
    builtin = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "debug"}}
        ]}}
    ]  # fmt: skip
    not_ours = trigger.Grader("Skill", r'"skill"\s*:\s*"ats-resume-tailor', 0, 0)
    assert trigger.grade(not_ours, builtin)  # an unrelated skill is not a failure
    assert not trigger.grade(not_ours, command)
    assert not trigger.grade(other, called)
    assert not trigger.grade(quiet, called)
    assert trigger.grade(quiet, [])
    assert not trigger.grade(wants, [])
    assert trigger.tool_calls(called, "Read") == ['{"file_path": "x"}']


def test_events_skip_lines_that_are_not_json_and_find_the_init_skills(
    trigger: ModuleType,
) -> None:
    stream = 'noise\n{"type": "system", "subtype": "init", "skills": ["b", "a"]}\n[1, 2]\n'
    items = trigger.events(stream)
    assert len(items) == 1
    assert trigger.visible_skills(items) == ["a", "b"]
    assert trigger.visible_skills([]) == []


def test_a_full_pass_with_a_fake_model_records_the_session(
    trigger: ModuleType, tmp_path: Path
) -> None:
    claude, args_file = fake(tmp_path)
    out = tmp_path / "last-run.json"
    argv = ["--claude", claude, "--out", str(out), "--runs", "2"]
    assert trigger.main(argv) == 0
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["model"] == "claude-sonnet-5-5"
    assert record["claude_code_version"] == "9.9.9"
    assert record["cost_usd"] == 0.14  # 14 runs at 0.01
    assert record["skills_visible_to_the_session"] == [SKILL]
    assert record["cases"]["fires-check-claims"] == {
        "expects": "fires",
        "runs": 2,
        "passed": 2,
        "errors": 0,
    }
    assert record["cases"]["quiet-job-search"]["passed"] == 2
    commands = [
        line for line in args_file.read_text(encoding="utf-8").splitlines() if "--model" in line
    ]
    assert len(commands) == 14
    assert all("--strict-mcp-config" in c and "--setting-sources project" in c for c in commands)
    assert all("--plugin-dir" in c and "--output-format stream-json" in c for c in commands)


def test_a_model_that_never_calls_the_skill_fails_the_fires_cases(
    trigger: ModuleType, tmp_path: Path
) -> None:
    claude, _ = fake(tmp_path, fires=False)
    out = tmp_path / "last-run.json"
    assert trigger.main(["--claude", claude, "--out", str(out), "--runs", "1"]) == 1
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["cases"]["fires-tailor-with-evidence"]["passed"] == 0
    assert record["cases"]["quiet-cover-letter"]["passed"] == 1


def test_the_spend_cap_stops_the_run_and_says_so(trigger: ModuleType, tmp_path: Path) -> None:
    claude, _ = fake(tmp_path)
    out = tmp_path / "last-run.json"
    argv = ["--claude", claude, "--out", str(out), "--runs", "3"]
    argv += ["--max-total-usd", "0.02", "--max-run-usd", "0.005"]
    assert trigger.main(argv) == 1
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["stopped_early"] is True
    assert len(record["runs"]) == 2
