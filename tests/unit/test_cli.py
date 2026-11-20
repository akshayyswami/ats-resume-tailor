from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ats_resume_tailor import __version__
from ats_resume_tailor.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_verify_passes_on_the_clean_resume(persona_path: Path, resume_path: Path) -> None:
    result = runner.invoke(app, ["verify", str(resume_path), "-e", str(persona_path)])
    assert result.exit_code == 0
    assert "verify: ok. 0 fail" in result.stdout


def test_verify_exits_1_and_names_the_rule(persona_path: Path, tmp_path: Path) -> None:
    resume = tmp_path / "bad.md"
    resume.write_text("## Experience\n\n- Led a team of 40 engineers. [E005]\n", encoding="utf-8")
    result = runner.invoke(app, ["verify", str(resume), "--evidence", str(persona_path)])
    assert result.exit_code == 1
    assert "bad.md:3: FAIL number-not-in-cited-evidence" in result.stdout
    assert "verify: FAIL. 1 fail" in result.stdout


def test_verify_json_output(persona_path: Path, tmp_path: Path) -> None:
    resume = tmp_path / "bad.md"
    resume.write_text("## Experience\n\n- Led a team. [E005]\n\n- No tag here.\n", encoding="utf-8")
    result = runner.invoke(app, ["verify", str(resume), "-e", str(persona_path), "--json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 1
    assert payload["ok"] is False
    assert {f["rule"] for f in payload["findings"]} == {"no-evidence-id", "weakly-checked"}


def test_verify_exits_2_when_the_bank_cannot_be_used(resume_path: Path, tmp_path: Path) -> None:
    bank = tmp_path / "bank.yaml"
    bank.write_text("facts: [{id: not-an-id, kind: role, text: x}]\n", encoding="utf-8")
    result = runner.invoke(app, ["verify", str(resume_path), "-e", str(bank)])
    assert result.exit_code == 2
    assert "evidence schema" in result.output


def test_verify_exits_2_on_duplicate_ids(resume_path: Path, tmp_path: Path) -> None:
    bank = tmp_path / "bank.yaml"
    fact = "{id: E001, kind: role, text: x, verified: {source: s, date: 2024-01-01}}"
    bank.write_text(f"facts: [{fact}, {fact}]\n", encoding="utf-8")
    result = runner.invoke(app, ["verify", str(resume_path), "-e", str(bank)])
    assert result.exit_code == 2
    assert "duplicate fact IDs: E001" in result.output


def test_a_missing_file_is_exit_2_not_a_traceback(persona_path: Path, tmp_path: Path) -> None:
    result = runner.invoke(app, ["verify", str(tmp_path / "nope.md"), "-e", str(persona_path)])
    assert result.exit_code == 2
    assert "cannot read" in result.output


def test_yaml_that_is_not_a_mapping_is_exit_2(tmp_path: Path) -> None:
    bank = tmp_path / "bank.yaml"
    bank.write_text("- just\n- a list\n", encoding="utf-8")
    result = runner.invoke(app, ["check-evidence", str(bank)])
    assert result.exit_code == 2


def test_check_evidence_clean_and_failing(persona_path: Path, tmp_path: Path) -> None:
    assert runner.invoke(app, ["check-evidence", str(persona_path)]).exit_code == 0
    bank = tmp_path / "bank.yaml"
    bank.write_text("facts: [{id: E001, kind: metric, text: Faster.}]\n", encoding="utf-8")
    result = runner.invoke(app, ["check-evidence", str(bank), "--json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 1
    assert sorted(f["rule"] for f in payload["findings"]) == [
        "metric-without-number",
        "missing-verified",
    ]


def test_init_writes_a_bank_that_passes_and_never_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "evidence.yaml"
    assert runner.invoke(app, ["init", str(path)]).exit_code == 0
    assert runner.invoke(app, ["check-evidence", str(path)]).exit_code == 0
    path.write_text("mine", encoding="utf-8")
    again = runner.invoke(app, ["init", str(path)])
    assert again.exit_code == 1
    assert path.read_text(encoding="utf-8") == "mine"
