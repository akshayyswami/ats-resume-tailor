from __future__ import annotations

from ats_resume_tailor.core.resume import parse


def test_header_block_is_everything_before_the_first_section() -> None:
    lines = parse("# Name\n\ncontact line\n\n## Experience\n\n- Did a thing. [E001]\n")
    assert [line.kind for line in lines] == ["header", "header", "heading", "claim"]


def test_claim_ids_are_split_from_the_body() -> None:
    [claim] = [line for line in parse("## Experience\n\n- Did a thing. [E001, E014]\n") if line.ids]
    assert claim.body == "Did a thing."
    assert claim.ids == ("E001", "E014")
    assert claim.has_ids


def test_a_claim_without_brackets_has_no_ids() -> None:
    [_, claim] = parse("## Experience\n\n- Did a thing.\n")
    assert claim.kind == "claim"
    assert not claim.has_ids


def test_empty_brackets_are_not_ids() -> None:
    [_, claim] = parse("## Experience\n\n- Did a thing. []\n")
    assert not claim.has_ids


def test_plain_paragraphs_after_a_section_are_claims() -> None:
    [_, paragraph] = parse("## Summary\n\nBackend engineer who ships.\n")
    assert paragraph.kind == "claim"


def test_skills_section_lines_are_skills_not_claims() -> None:
    lines = parse("## Skills\n\n- Python, Go\n\n## Technical Skills\n\n- Kafka\n")
    assert [line.kind for line in lines if line.kind != "heading"] == ["skills", "skills"]


def test_heading_levels_and_line_numbers() -> None:
    lines = parse("# Name\n\n## Experience\n\n### Role, Co (2021 to 2024)\n")
    assert [(line.level, line.number) for line in lines] == [(1, 1), (2, 3), (3, 5)]
    assert lines[1].section == "experience"
