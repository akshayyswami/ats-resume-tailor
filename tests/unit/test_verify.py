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
    assert len(ALL_RULES) == len(set(ALL_RULES)) == 21


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


def header_rules(text: str, bank: Evidence, *, status: str = "FAIL") -> list[tuple[str, int]]:
    report = verify(text, bank)
    return [(f.rule, f.line) for f in report.findings if f.status == status]


BODY = "\n## Experience\n\n- Cut p95 latency from 900 ms to 240 ms. [E002]\n"


def test_a_header_with_a_name_and_contact_details_passes(persona: Evidence) -> None:
    contact = "+1 (555) 010-0199 | jordan.lee@example.com | Example City | linkedin.com/in/jordan"
    assert header_rules(f"# Jordan Lee\n\n{contact}\n{BODY}", persona) == []


def test_a_skill_a_figure_or_a_years_claim_in_the_header_fails(persona: Evidence) -> None:
    for line in (
        "Rust and Go engineer",
        "Grew revenue by 900%",
        "Saved $2M a year",
        "Over 10 years of experience",
        "Cut cost 3x",
    ):
        assert ("claim-in-header", 3) in header_rules(f"# Jordan Lee\n\n{line}\n{BODY}", persona)


def test_a_bullet_or_sub_heading_before_the_first_section_fails(persona: Evidence) -> None:
    for line in ("- Led a team", "### Backend Engineer"):
        assert ("claim-in-header", 3) in header_rules(f"# Jordan Lee\n\n{line}\n{BODY}", persona)


def test_a_long_header_line_with_nothing_to_check_is_reported_not_checked(
    persona: Evidence,
) -> None:
    prose = "A thoughtful and careful engineer who enjoys clear writing and calm teams"
    text = f"# Jordan Lee\n\n{prose}\n{BODY}"
    assert header_rules(text, persona) == []
    assert header_rules(text, persona, status="NOT_CHECKED")[0][0] == "header-prose"


def test_a_resume_with_no_claim_lines_fails_instead_of_passing(persona: Evidence) -> None:
    assert header_rules("# Jordan Lee\n\nexample city\n", persona) == [("no-claims", 0)]
    assert ("no-claims", 0) in header_rules("# Jordan Lee\n\n### Role\n\nsome text\n", persona)
    assert ("no-claims", 0) not in header_rules(f"# Jordan Lee\n\nexample city\n{BODY}", persona)
    assert header_rules("## Skills\n\n- Python\n", persona) == []  # a skills list is a body


def test_invisible_characters_fail_and_do_not_hide_the_word(persona: Evidence) -> None:
    for hidden in ("​", "­", "⁠", "﻿", "‮"):
        text = f"# Jordan Lee\n\n## Experience\n\n- Wrote Ru{hidden}st code. [E004]\n"
        found = {rule for rule, _ in header_rules(text, persona)}
        assert found == {"hidden-characters", "not-claimable-term"}, hidden


def test_fullwidth_lookalikes_are_folded_before_matching(persona: Evidence) -> None:
    text = "# Jordan Lee\n\n## Experience\n\n- Wrote \uff32ust code. [E004]\n"
    assert ("not-claimable-term", 5) in header_rules(text, persona)
