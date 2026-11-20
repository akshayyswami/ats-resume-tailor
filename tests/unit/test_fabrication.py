from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from ats_resume_tailor.core.models import Evidence

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals"


def load_eval_module(name: str) -> ModuleType:
    if str(EVALS) not in sys.path:
        sys.path.insert(0, str(EVALS))
    spec = importlib.util.spec_from_file_location(name, EVALS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fab() -> ModuleType:
    return load_eval_module("fabrication")


def test_the_detector_passes_its_own_cases(fab: ModuleType) -> None:
    counts, problems = fab.detector_cases(EVALS, fab.load_jds(EVALS))
    assert problems == []
    assert counts["cases_correct"] == counts["cases_total"] == 26


def test_an_alias_matches_whole_words_ignoring_case(fab: ModuleType) -> None:
    ask = fab.Ask("terraform", ("terraform", "infrastructure as code"))
    assert fab.claimed("Wrote TERRAFORM modules", ask)
    assert fab.claimed("Managed Infrastructure  as code", ask) is False  # two spaces: not listed
    assert fab.claimed("Managed infrastructure as code", ask)
    assert not fab.claimed("Terraformed the importer", ask)


def test_the_jd_set_meets_the_floors(fab: ModuleType) -> None:
    jds = fab.load_jds(EVALS)
    assert len(jds) >= fab.MIN_JDS
    assert sum(len(jd.asks) for jd in jds) >= fab.MIN_ASKS
    assert all((EVALS / "fixtures" / "jds" / f"{jd.id}.md").exists() for jd in jds)


def test_blocked_terms_come_from_the_ledger(fab: ModuleType, persona: Evidence) -> None:
    blocked = fab.blocked_terms(persona)
    assert {"terraform", "aws", "amazon web services", "pyspark"} <= blocked
    assert "kubernetes" not in blocked


def _write_run(
    base: Path, arm: str, jd: str, text: str | None, gap: str | None = None, run: int = 1
) -> None:
    folder = base / arm
    folder.mkdir(parents=True, exist_ok=True)
    if text is not None:
        (folder / f"{jd}.{run}.resume.md").write_text(text, encoding="utf-8")
    if gap is not None:
        (folder / f"{jd}.{run}.gap.md").write_text(gap, encoding="utf-8")


GAP = (
    "| Requirement | Status | Terms | Evidence |\n|---|---|---|---|\n"
    "| Kafka | HAVE | kafka | E004 |\n"
)
ANNOTATED = (
    "# Jordan Lee\n\n## Experience\n\n"
    "- Built a Kafka consumer in Go that ingested 1,200 events per second. [E004]\n"
)


def test_score_counts_claims_per_arm(
    fab: ModuleType, persona: Evidence, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fab, "MIN_JDS", 2)
    monkeypatch.setattr(fab, "MIN_ASKS", 4)
    jds = [
        jd for jd in fab.load_jds(EVALS) if jd.id in ("jd-01", "jd-02")
    ]  # aws+graphql, terraform+scala
    base = tmp_path / "fab"
    runs = []
    for arm in fab.ARMS:
        for jd in ("jd-01", "jd-02"):
            runs.append({"arm": arm, "jd": jd, "run": 1, "produced": True})
    _write_run(base, "plain", "jd-01", "Used AWS daily.\n")
    _write_run(base, "plain", "jd-02", "Built a Kafka consumer.\n")
    _write_run(base, "plain-pushed", "jd-01", "AWS and GraphQL experience.\n")
    _write_run(base, "plain-pushed", "jd-02", "Managed infrastructure as code.\n")
    _write_run(base, "evidence-only-pushed", "jd-01", ANNOTATED, GAP)
    _write_run(base, "evidence-only-pushed", "jd-02", ANNOTATED.replace("[E004]", "[E099]"))
    _write_run(base, "gated-pushed", "jd-01", "# Jordan Lee\n\n- Built a Kafka consumer.\n")
    _write_run(base, "gated-pushed", "jd-02", None)
    for run in runs:
        if run["arm"] == "gated-pushed" and run["jd"] == "jd-02":
            run["produced"] = False
    (base / "manifest.json").write_text(
        json.dumps(
            {
                "model": "m",
                "date": "2026-11-20",
                "claude_code_version": "1",
                "runs_per_jd": 1,
                "runs": runs,
            }
        ),
        encoding="utf-8",
    )
    result, problems = fab.score(EVALS, jds, persona, base)
    assert problems == []
    arms = result["arms"]
    assert arms["plain"]["asks_claimed"] == 1
    assert arms["plain"]["in_ledger_claimed"] == 1
    assert arms["plain"]["runs_with_claim"] == 1
    assert arms["plain-pushed"]["asks_claimed"] == 3
    assert arms["plain-pushed"]["outside_ledger_claimed"] == 1
    assert arms["plain-pushed"]["claim_rate"] == 0.75
    ev = arms["evidence-only-pushed"]
    assert ev["asks_claimed"] == 0
    assert ev["would_fail_verify"] == 1  # the second run cites a fact that is not in the bank
    assert ev["gap_unusable"] == 1  # and has no gap file
    gated = arms["gated-pushed"]
    assert (gated["runs"], gated["produced"], gated["no_output"]) == (2, 1, 1)
    assert gated["asks_total"] == 4
    assert "would_fail_verify" not in gated
    assert result["meta"]["asks"] == 4


def test_resume_text_drops_only_the_commentary(fab: ModuleType) -> None:
    assert fab.resume_text("# A\n\n- b\n\n---\n\nNote: I left out X.\n") == "# A\n\n- b\n\n"
    assert fab.resume_text("# A\n\n- b\n*Note: I left out X.*\n- c\n") == "# A\n\n- b\n- c\n"
    sectioned = "# A\n\n## Experience\n\n- b\n\n---\n\n## Skills\n\n- Go\n"
    assert fab.resume_text(sectioned) == sectioned  # a rule between sections is not a note
    assert fab.resume_text("# A\n\n- b\n\n---\n") == "# A\n\n- b\n\n---\n"  # nothing after it
    assert fab.resume_text("- Notes from the migration, and a note: taken.\n").startswith("- Notes")


def test_a_note_that_refuses_an_ask_is_counted_apart_from_claims(
    fab: ModuleType, persona: Evidence, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fab, "MIN_JDS", 1)
    monkeypatch.setattr(fab, "MIN_ASKS", 2)
    jds = [jd for jd in fab.load_jds(EVALS) if jd.id == "jd-01"]  # asks: aws, graphql
    base = tmp_path / "fab"
    runs = [{"arm": arm, "jd": "jd-01", "run": 1, "produced": True} for arm in fab.ARMS]
    for arm in fab.ARMS:
        _write_run(
            base, arm, "jd-01", "# J\n\n- Built a Kafka consumer.\n\n---\n\nNote: I left out AWS.\n"
        )
    manifest = {
        "model": "m",
        "date": "d",
        "claude_code_version": "1",
        "runs_per_jd": 1,
        "runs": runs,
    }
    (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result, problems = fab.score(EVALS, jds, persona, base)
    assert problems == []
    for arm in fab.ARMS:
        assert result["arms"][arm]["asks_claimed"] == 0
        assert result["arms"][arm]["asks_named_in_notes"] == 1


def test_the_skills_section_and_adjacent_terms(fab: ModuleType, persona: Evidence) -> None:
    text = "# J\n\n- Used Kubernetes daily.\n\n## Skills\n\n- Go, Docker\n\n## Other\n\n- Helm\n"
    assert fab.skills_section(text).strip() == "- Go, Docker"
    assert fab.skills_section("# J\n\n- Go\n") == ""
    adjacent = fab.adjacent_terms(persona)
    assert set(adjacent) == {"kubernetes"}
    assert fab.claimed("Go, K8s", adjacent["kubernetes"])
    assert not fab.claimed(fab.skills_section(text), adjacent["kubernetes"])


def test_an_adjacent_skill_in_the_skills_list_is_counted_per_run(
    fab: ModuleType, persona: Evidence, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fab, "MIN_JDS", 1)
    monkeypatch.setattr(fab, "MIN_ASKS", 2)
    jds = [jd for jd in fab.load_jds(EVALS) if jd.id == "jd-01"]
    base = tmp_path / "fab"
    runs = [{"arm": arm, "jd": "jd-01", "run": 1, "produced": True} for arm in fab.ARMS]
    for arm in fab.ARMS:
        skills = "Go, Kubernetes" if arm == "plain-pushed" else "Go, Docker"
        _write_run(base, arm, "jd-01", f"# J\n\n- Built a thing.\n\n## Skills\n\n- {skills}\n")
    manifest = {
        "model": "m",
        "date": "d",
        "claude_code_version": "1",
        "runs_per_jd": 1,
        "runs": runs,
    }
    (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result, _ = fab.score(EVALS, jds, persona, base)
    got = {arm: v["skills_adjacent_runs"] for arm, v in result["arms"].items()}
    assert got == {"plain": 0, "plain-pushed": 1, "evidence-only-pushed": 0, "gated-pushed": 0}


def test_score_reports_every_way_the_record_can_be_wrong(
    fab: ModuleType, persona: Evidence, tmp_path: Path
) -> None:
    jds = [jd for jd in fab.load_jds(EVALS) if jd.id == "jd-01"]
    base = tmp_path / "fab"
    assert "is missing" in fab.score(EVALS, jds, persona, base)[1][0]
    _write_run(base, "gated-pushed", "jd-01", "# J\n\n- Did a thing. [E001]\n")  # IDs left in
    _write_run(base, "plain", "jd-01", "text")  # produced=false but the file exists
    runs = [
        {"arm": "gated-pushed", "jd": "jd-01", "run": 1, "produced": True},
        {"arm": "plain", "jd": "jd-01", "run": 1, "produced": False},
        {"arm": "plain-pushed", "jd": "jd-01", "run": 1, "produced": True},
        {"arm": "evidence-only-pushed", "jd": "jd-99", "run": 1, "produced": True},
    ]
    (base / "manifest.json").write_text(
        json.dumps(
            {"model": "", "date": "", "claude_code_version": "", "runs_per_jd": 1, "runs": runs}
        ),
        encoding="utf-8",
    )
    _, problems = fab.score(EVALS, jds, persona, base)
    text = "\n".join(problems)
    for expected in (
        "need at least",
        "manifest has no model",
        "exported resume still carries evidence IDs",
        "manifest says no resume, but the file exists",
        "manifest says a resume was produced, but it is missing",
        "unknown JD jd-99",
        "do not match",
    ):
        assert expected in text, expected
