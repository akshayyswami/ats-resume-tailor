from __future__ import annotations

import pytest

from ats_resume_tailor.core.numbers import canonical_values, extract, quantity_words


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1,200 events", {"1200"}),
        ("1200 events", {"1200"}),
        ("cut it by 40%", {"40%"}),
        ("cut it by 40 percent", {"40%"}),
        ("cut it by 40 per cent", {"40%"}),
        ("$1.2M in savings", {"1200000"}),
        ("10k users", {"10000"}),
        ("a 3x speedup", {"3x"}),
        ("from 4 hours to 35 minutes", {"4", "35"}),
        ("0.50 of the load", {"0.5"}),
        ("3-5 engineers", {"3", "5"}),
    ],
)
def test_canonical_values(text: str, expected: set[str]) -> None:
    assert canonical_values(text) == expected


@pytest.mark.parametrize("text", ["p95 latency", "EC2 instances", "S3 buckets", "no digits here"])
def test_numbers_glued_to_letters_are_labels(text: str) -> None:
    assert extract(text) == []


def test_a_space_before_m_is_not_a_million() -> None:
    # "10 m" and "35 minutes" must not turn into 10,000,000 and 35,000,000.
    assert canonical_values("35 minutes") == {"35"}
    assert canonical_values("10 m wide") == {"10"}


def test_mention_keeps_the_raw_text() -> None:
    [mention] = extract("saved $1.2M last year")
    assert mention.raw == "$1.2M"
    assert mention.value == "1200000"


def test_quantity_words_are_found_case_insensitively() -> None:
    assert quantity_words("Doubled throughput and cut costs by dozens of hours") == [
        "doubled",
        "dozens",
    ]
    assert quantity_words("a plain sentence") == []
