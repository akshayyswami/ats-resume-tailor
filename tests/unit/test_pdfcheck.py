from __future__ import annotations

import pytest

from ats_resume_tailor.core.pdfcheck import (
    MIN_HEADER_RECALL,
    MIN_PAIR_RECALL,
    MIN_TOKEN_RECALL,
    PDF_RULES,
    Extraction,
    PdfError,
    check_pdf,
    header_words,
    missing,
    recall,
    source_words,
    words,
)

SOURCE = (
    "# Jordan Lee\n\njordan.lee@example.com | Example City\n\n## Experience\n\n"
    "- Built a Kafka consumer in Go that ingested 1,200 events per second from carrier "
    "webhooks and wrote the retry logic for failed deliveries. [E004]\n"
    "- Cut p95 latency of the shipment lookup API from 900 ms to 240 ms with a covering "
    "index and a read replica. [E002, E003]\n"
)


def extraction(stream: str, visual: str | None = None, *, images: int = 0) -> Extraction:
    return Extraction(
        stream=stream, visual=stream if visual is None else visual, pages=1, images=images
    )


def clean_text() -> str:
    return " ".join(source_words(SOURCE))


def rules(text: Extraction) -> list[str]:
    return [f.rule for f in check_pdf(SOURCE, text).findings]


def test_words_fold_ligatures_case_and_punctuation() -> None:
    assert words("Efﬁcient, e-mail: 1,200 ms") == ["efficient", "e", "mail", "1", "200", "ms"]


def test_the_source_loses_evidence_ids_and_link_targets() -> None:
    text = "- Wrote [the guide](https://example.com/x) for 12 engineers. [E011, E012]"
    assert source_words(text) == ["wrote", "the", "guide", "for", "12", "engineers"]


def test_header_words_stop_at_the_first_level_two_heading() -> None:
    assert header_words(SOURCE) == [
        "jordan",
        "lee",
        "jordan",
        "lee",
        "example",
        "com",
        "example",
        "city",
    ]
    assert header_words("## Summary\n\n- a b c\n") == []


def test_recall_counts_repeats_by_multiplicity() -> None:
    assert recall(["a", "a", "b"], ["a", "b"], 1) == pytest.approx(2 / 3)
    assert recall(["a", "b", "c"], ["a", "b", "c"], 2) == 1.0
    assert recall(["a", "b", "c"], ["a", "c", "b"], 2) == 0.0
    assert recall(["a"], [], 2) == 1.0  # no pairs to lose in a one-word source


def test_missing_lists_distinct_words_in_source_order_and_stops_at_the_limit() -> None:
    assert missing(["x", "a", "b", "x", "c"], ["a"], limit=10) == ["x", "b", "c"]
    assert missing(["x", "y", "z"], [], limit=2) == ["x", "y"]


def test_a_clean_round_trip_passes() -> None:
    report = check_pdf(SOURCE, extraction(clean_text()))
    assert report.ok
    assert {(r.token, r.header, r.pair) for r in report.recalls} == {(1.0, 1.0, 1.0)}
    assert report.source_words == len(source_words(SOURCE))


def test_no_text_at_all_is_one_finding_whatever_the_images() -> None:
    assert rules(extraction("")) == ["no-extractable-text"]
    assert rules(extraction("", images=3)) == ["no-extractable-text"]
    assert rules(extraction("jordan lee")) == ["no-extractable-text"]  # under 20 words


def test_a_tiny_source_is_not_called_empty() -> None:
    report = check_pdf("# A B\n\nc d e\n", extraction("a b c d e"))
    assert report.ok


def test_missing_words_with_images_is_text_in_images() -> None:
    body = " ".join(source_words(SOURCE)[8:])  # everything except the header
    assert rules(extraction(body, images=1)) == ["text-in-images"]


def test_missing_words_without_images_is_low_token_recall() -> None:
    body = " ".join(source_words(SOURCE)[8:])
    assert rules(extraction(body)) == ["low-token-recall"]


def test_a_missing_header_fails_even_when_overall_recall_is_high() -> None:
    long_body = " ".join(["filler"] * 400)
    source = f"# Jordan Lee\n\n## Experience\n\n- {long_body}\n"
    got = extraction(long_body)
    report = check_pdf(source, got)
    assert report.recalls[0].token > MIN_TOKEN_RECALL  # 400 of 402 words come back
    assert [f.rule for f in report.findings] == ["low-token-recall"]
    assert "name and contact" in report.findings[0].message
    with_image = check_pdf(source, extraction(long_body, images=1))
    assert [f.rule for f in with_image.findings] == ["text-in-images"]


def test_an_image_alone_is_not_a_failure() -> None:
    assert rules(extraction(clean_text(), images=2)) == []


def test_columns_read_straight_across_break_the_reading_order() -> None:
    words_in_order = source_words(SOURCE)
    jumbled = words_in_order[:8] + words_in_order[8::2] + words_in_order[9::2]
    got = extraction(clean_text(), " ".join(jumbled))
    report = check_pdf(SOURCE, got)
    assert [f.rule for f in report.findings] == ["reading-order-broken"]
    assert "visual line order" in report.findings[0].message
    assert report.recalls[0].pair == 1.0
    assert report.recalls[1].token == 1.0
    assert report.recalls[1].pair < MIN_PAIR_RECALL


def test_either_order_failing_is_reported_by_name() -> None:
    words_in_order = source_words(SOURCE)
    jumbled = " ".join(words_in_order[:8] + words_in_order[8::2] + words_in_order[9::2])
    both = check_pdf(SOURCE, extraction(jumbled))
    assert [f.message.split(",")[0] for f in both.findings] == [
        "in stream order",
        "in visual line order",
    ]
    assert "draws its text out of reading order" in both.findings[0].message
    assert "Columns, text boxes and tables" in both.findings[1].message


def test_thresholds_are_inclusive_and_stated() -> None:
    assert (MIN_TOKEN_RECALL, MIN_PAIR_RECALL, MIN_HEADER_RECALL) == (0.95, 0.95, 1.0)
    # 101 source words: "h", "s" and w0 to w98. Dropping the last 5 leaves token recall 0.9505 and
    # pair recall exactly 0.95. Dropping the last 6 leaves token recall 0.9406.
    body = [f"w{n}" for n in range(99)]
    source = "# H\n\n## S\n\n- " + " ".join(body)
    exact = check_pdf(source, extraction(" ".join(["h", "s", *body[:94]])))
    assert exact.recalls[0].token == 0.9505
    assert exact.recalls[0].pair == 0.95
    assert exact.ok
    below = check_pdf(source, extraction(" ".join(["h", "s", *body[:93]])))
    assert [f.rule for f in below.findings] == ["low-token-recall"]


def test_an_empty_source_is_an_input_error() -> None:
    with pytest.raises(PdfError, match="no words"):
        check_pdf("## \n\n[E001]\n", extraction("a"))


def test_every_pdf_rule_is_named_once() -> None:
    assert len(PDF_RULES) == len(set(PDF_RULES)) == 4
