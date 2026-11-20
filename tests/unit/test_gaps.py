from __future__ import annotations

import pytest

from ats_resume_tailor.core.gaps import GapError, parse_gaps
from ats_resume_tailor.core.models import Evidence
from ats_resume_tailor.core.verify import verify
from tests.conftest import resume_with

TABLE = """\
| Requirement | Status | Terms | Evidence |
|---|---|---|---|
| Python services | have | Python, Go | E001, E012 |
| GraphQL APIs | MISSING | GraphQL | |
| Leading a team | PARTIAL | | E005 |

Lead: E002, because the posting opens with lookups.
"""


def test_parse_reads_rows_terms_and_lead() -> None:
    table = parse_gaps(TABLE)
    assert [row.status for row in table.rows] == ["HAVE", "MISSING", "PARTIAL"]
    assert table.rows[0].terms == ("python", "go")
    assert table.rows[0].evidence == ("E001", "E012")
    assert table.terms() == ["go", "graphql", "python"]
    assert table.missing_terms() == {"graphql"}
    assert table.lead == "E002, because the posting opens with lookups."


def test_a_bolded_lead_line_is_read() -> None:
    table = parse_gaps(TABLE.replace("Lead:", "**Lead**:"))
    assert table.lead.startswith("E002")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("no table here\n", "no gap table found"),
        ("| A | B |\n|---|---|\n| x | HAVE |\n", "table header must be"),
        (TABLE.replace("MISSING", "UNKNOWN"), "status must be HAVE, PARTIAL or MISSING"),
        (TABLE.replace("| GraphQL |", "| GraphQL | extra |"), "expected 4 columns"),
        ("| Requirement | Status | Terms | Evidence |\n|---|---|---|---|\n", "no gap table found"),
    ],
)
def test_a_malformed_table_is_an_error(text: str, message: str) -> None:
    with pytest.raises(GapError, match=message):
        parse_gaps(text)


def test_a_missing_requirement_term_fails_anywhere(persona: Evidence) -> None:
    table = parse_gaps(TABLE)
    bullet = resume_with("- Cut latency from 900 ms to 240 ms behind a GraphQL gateway. [E002]")
    rules = [f.rule for f in verify(bullet, persona, table).failures]
    assert "missing-requirement-claimed" in rules
    skills = [f.rule for f in verify("## Skills\n\n- Python, GraphQL\n", persona, table).failures]
    assert "missing-requirement-claimed" in skills
    heading = "## Experience\n\n### GraphQL Engineer, Co\n\n- Wrote a guide. [E011]\n"
    assert "missing-requirement-claimed" in [
        f.rule for f in verify(heading, persona, table).failures
    ]


def test_a_gap_alias_resolves_to_the_ledger_term(persona: Evidence) -> None:
    table = parse_gaps(TABLE.replace("GraphQL | |", "k8s | |"))
    text = resume_with("- Ran the Kubernetes cluster that hosted 2 services. [E007]")
    assert "missing-requirement-claimed" in [f.rule for f in verify(text, persona, table).failures]


def test_a_requirement_term_no_fact_supports_fails_in_a_bullet(persona: Evidence) -> None:
    table = parse_gaps(
        "| Requirement | Status | Terms | Evidence |\n|---|---|---|---|\n"
        "| Scheduled pipelines on Airflow | PARTIAL | airflow | E010 |\n"
    )
    text = resume_with("- Ran 3 scripts on Airflow. [E010]")
    assert [f.rule for f in verify(text, persona, table).failures] == ["term-not-in-cited-evidence"]
    # Without the gap file the checker has never heard of the term, so it can only say not checked.
    assert verify(text, persona).ok


def test_the_same_resume_passes_when_it_stays_clear_of_missing_terms(persona: Evidence) -> None:
    table = parse_gaps(TABLE)
    assert verify(resume_with("- Led a team of 4 engineers. [E005]"), persona, table).ok
