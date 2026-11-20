from __future__ import annotations

from pathlib import Path

import pytest

from ats_resume_tailor.core.gaps import parse_gaps
from ats_resume_tailor.core.models import Evidence, EvidenceError
from ats_resume_tailor.core.verify import ALL_RULES, check_evidence, verify
from tests.conftest import resume_with


def rules(text: str, bank: Evidence, *, status: str = "FAIL") -> list[str]:
    report = verify(text, bank)
    return [f.rule for f in report.findings if f.status == status]


def test_the_clean_persona_resume_passes(persona: Evidence, resume_path: Path) -> None:
    report = verify(resume_path.read_text(encoding="utf-8"), persona)
    assert report.ok
    assert report.findings == ()
    assert report.claim_lines == 10
    assert report.skill_items == 1
    assert report.unchecked_headings == 2


def test_a_bullet_citing_two_facts_may_use_numbers_from_either(persona: Evidence) -> None:
    text = resume_with("- Cut latency from 900 ms to 240 ms and pages by 30%. [E002, E008]")
    assert rules(text, persona) == []


def test_sanctioned_adjacent_wording_passes_only_with_a_supporting_fact(persona: Evidence) -> None:
    wording = "deployed 2 services onto a Kubernetes cluster run by the platform team"
    assert rules(resume_with(f"- I {wording}. [E007]"), persona) == []
    # Same wording, but citing a fact the ledger does not name as support.
    assert "adjacent-term-overclaim" in rules(resume_with(f"- I {wording}. [E006]"), persona)


def test_a_word_the_cited_fact_says_is_supported_even_when_it_is_not_a_tag(
    persona: Evidence,
) -> None:
    gaps = parse_gaps(
        "| Requirement | Status | Terms | Evidence |\n|---|---|---|---|\n"
        "| Fewer pages | HAVE | on-call, retries | E008 |\n\nLead: E008, because of on-call.\n"
    )
    said = "- Reduced on-call pages by 30% with retries and backoff and an alert on queue depth."
    said += " [E008]"
    assert verify(resume_with(said), persona, gaps).ok
    # The same word on a bullet whose cited fact does not say it is still a failure.
    other = (
        "- Cut p95 latency of the shipment lookup API from 900 ms to 240 ms with retries. [E002]"
    )
    failed = [f.rule for f in verify(resume_with(other), persona, gaps).failures]
    assert failed == ["term-not-in-cited-evidence"]


def test_adjacent_term_cannot_stand_alone_in_a_skills_list(persona: Evidence) -> None:
    assert rules("## Skills\n\n- Python, Kubernetes\n", persona) == ["adjacent-term-overclaim"]


def test_an_alias_is_the_same_term(persona: Evidence) -> None:
    text = resume_with("- Moved the job to PySpark, cutting it from 4 hours to 35 minutes. [E003]")
    assert rules(text, persona) == ["not-claimable-term"]
    assert rules(resume_with("- Tuned a Postgres index. [E002]"), persona) == []


def test_a_not_claimable_term_fails_in_a_role_heading(persona: Evidence) -> None:
    text = "# N\n\n## Experience\n\n### Terraform Engineer, Co\n\n- Wrote the guide. [E011]\n"
    assert rules(text, persona) == ["not-claimable-term"]


def test_a_skills_label_is_ignored(persona: Evidence) -> None:
    assert rules("## Skills\n\n- Languages: Python, Go\n", persona) == []


def test_unknown_skill_in_the_list_fails_closed(persona: Evidence) -> None:
    assert rules("## Skills\n\n- Python, Elixir\n", persona) == ["unsupported-skill"]


def test_a_term_outside_the_lexicon_in_a_bullet_is_not_checked_not_failed(
    persona: Evidence,
) -> None:
    text = resume_with("- Ran weekly demos for the Elixir guild. [E011]")
    report = verify(text, persona)
    assert report.ok
    assert [f.rule for f in report.not_checked] == ["weakly-checked"]


def test_quantity_words_are_reported_not_checked(persona: Evidence) -> None:
    report = verify(resume_with("- Doubled the throughput of the lookup API. [E002]"), persona)
    assert report.ok
    assert [f.rule for f in report.not_checked] == ["quantity-word", "weakly-checked"]


def test_a_quantity_word_the_fact_itself_uses_is_fine() -> None:
    bank = Evidence.model_validate(
        {
            "facts": [
                {
                    "id": "E001",
                    "kind": "project",
                    "text": "Halved the build time.",
                    "verified": {"source": "ci history", "date": "2024-01-01"},
                }
            ]
        }
    )
    report = verify(resume_with("- Halved the build time. [E001]"), bank)
    assert [f.rule for f in report.not_checked] == ["weakly-checked"]


def test_a_cited_unverified_fact_does_not_lend_its_numbers(persona: Evidence) -> None:
    facts = [*persona.facts, persona.facts[0].model_copy(update={"id": "E050", "verified": None})]
    bank = persona.model_copy(update={"facts": facts})
    assert "unverified-evidence-cited" in rules(resume_with("- Did a thing. [E050]"), bank)


def test_banned_words_match_whole_words_only(persona: Evidence) -> None:
    assert rules(resume_with("- Wrote a robustness test for the API. [E002]"), persona) == []
    assert rules(resume_with("- Wrote a robust retry policy. [E008]"), persona) == ["banned-word"]


def test_duplicate_ids_stop_verify(persona: Evidence) -> None:
    bank = persona.model_copy(update={"facts": [*persona.facts, persona.facts[0]]})
    with pytest.raises(EvidenceError, match="E001"):
        verify(resume_with("- Did a thing. [E001]"), bank)


def test_rule_names_are_unique() -> None:
    assert len(ALL_RULES) == len(set(ALL_RULES)) == 18


def test_check_evidence_is_clean_on_the_persona(persona: Evidence) -> None:
    assert check_evidence(persona) == []


def test_adjacent_ledger_entries_are_checked_for_completeness(persona: Evidence) -> None:
    ledger = [
        entry.model_copy(update={"say_instead": "ran it", "supported_by": ["E404"]})
        if entry.term == "kubernetes"
        else entry
        for entry in persona.ledger
    ]
    findings = check_evidence(persona.model_copy(update={"ledger": ledger}))
    [finding] = findings
    assert finding.rule == "adjacent-incomplete"
    assert "does not contain the term" in finding.message
    assert "E404" in finding.message
