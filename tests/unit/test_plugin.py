"""The plugin files agree with the package and with each other. Offline, no Claude Code needed."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from ats_resume_tailor import __version__

ROOT = Path(__file__).resolve().parents[2]


def front_matter(path: Path) -> dict[str, str]:
    match = re.match(r"\A---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.DOTALL)
    assert match, f"{path} has no front matter"
    pairs = (line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def test_the_versions_agree_everywhere_they_appear() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert plugin["version"] == project["version"] == __version__
    assert plugin["name"] == project["name"]


def test_the_repo_is_its_own_marketplace_for_the_plugin() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    (entry,) = market["plugins"]
    assert entry["name"] == plugin["name"]
    assert entry["source"] == "./"
    assert market["owner"]["name"]


def test_every_command_has_a_description_and_the_three_expected_ones_exist() -> None:
    names = {path.stem for path in (ROOT / "commands").glob("*.md")}
    assert names == {"tailor", "verify", "pdf-check"}
    for path in (ROOT / "commands").glob("*.md"):
        meta = front_matter(path)
        assert meta["description"], path
        assert meta["argument-hint"], path
        assert "$ARGUMENTS" in path.read_text(encoding="utf-8"), path


def test_the_skill_says_when_to_use_it_and_when_not_to() -> None:
    description = front_matter(ROOT / "skills" / "ats-resume-tailor" / "SKILL.md")["description"]
    assert description.startswith("Use when")
    assert "Do not use for" in description


def test_the_wrapper_is_executable_and_explains_a_missing_project() -> None:
    wrapper = ROOT / "bin" / "ats-resume-tailor"
    assert os.access(wrapper, os.X_OK)
    text = wrapper.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert "uv tool install git+https://github.com/akshayyswami/ats-resume-tailor" in text
    assert "UV_PROJECT_ENVIRONMENT" in text  # no virtualenv inside the plugin folder


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")
def test_the_wrapper_runs_the_command_from_another_folder(tmp_path: Path) -> None:
    env = {**os.environ, "XDG_CACHE_HOME": str(tmp_path / "cache")}
    done = subprocess.run(  # noqa: S603
        [str(ROOT / "bin" / "ats-resume-tailor"), "version"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
        timeout=300,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == __version__
    assert (tmp_path / "cache" / "ats-resume-tailor" / "venv").is_dir()
    assert not (ROOT / "bin" / ".venv").exists()


def test_the_recorded_trigger_run_passed_and_matches_the_current_descriptions() -> None:
    from tests.unit.test_fabrication import load_eval_module

    load_eval_module("fabrication")
    trigger = load_eval_module("run_trigger")
    record = json.loads((ROOT / "skill-evals" / "last-run.json").read_text(encoding="utf-8"))
    assert record["descriptions_sha256"] == trigger.description_hash(), (
        "a description changed since the last trigger run: run evals/run_trigger.py again"
    )
    assert not record["stopped_early"]
    cases = record["cases"]
    assert len(cases) == len(trigger.load_cases(ROOT / "skill-evals"))
    assert all(c["passed"] == c["runs"] > 0 and c["errors"] == 0 for c in cases.values())
