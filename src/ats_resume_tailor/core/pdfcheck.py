"""The PDF round-trip check: does a resume survive being read back out of its PDF?

An ATS does not look at the page. It pulls the text out of the file and works from that. This
check takes the text a PDF gives back, in two reading orders, and compares it with the resume the
PDF was made from. Pure: it takes strings and counts, and the adapter does the reading.

Two numbers, both measured against the source resume:

- token recall: the share of the resume's words that come back. It falls when text is missing,
  garbled or locked in an image.
- header recall: the share of the words in the header block (everything before the first `## `
  heading, so the name and contact lines) that come back. An ATS reads those to identify the
  applicant, and a few words are too small a share of the whole for token recall to notice.
- pair recall: the share of the resume's adjacent word pairs that come back as pairs. It falls
  when the reading order is scrambled, for example by columns read straight across.

Two reading orders, because parsers differ. Stream order is the order the PDF draws its text.
Visual order is top to bottom, left to right, line by line. A two-column PDF is often clean in the
first and interleaved in the second, so a check that ran only one would miss it.

Passing means the text survives these two readings. It does not mean a given ATS parses the file.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from ats_resume_tailor.core.models import EvidenceError
from ats_resume_tailor.core.verify import Finding

PDF_RULES: Final = (
    "no-extractable-text",
    "text-in-images",
    "low-token-recall",
    "reading-order-broken",
)

# Calibrated on the fixtures in evals/fixtures/pdfs, from one 200-word resume: the clean PDFs
# score 1.0, the weakest failing one scores 0.864. The check prints the measured values, so a
# result near a threshold can be judged by hand.
MIN_TOKEN_RECALL: Final = 0.95
MIN_PAIR_RECALL: Final = 0.95
MIN_HEADER_RECALL: Final = 1.0
MIN_WORDS: Final = 20
MISSING_SHOWN: Final = 8
DIGITS: Final = 4

STREAM: Final = "stream order"
VISUAL: Final = "visual line order"
ORDER_ADVICE: Final = {
    STREAM: "The file draws its text out of reading order, so a parser that follows the "
    "drawing order gets it scrambled",
    VISUAL: "Columns, text boxes and tables are the usual cause",
}

_EVIDENCE_TAG = re.compile(r"\[E\d+(?:\s*,\s*E\d+)*\]")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_WORD = re.compile(r"[^\W_]+")


class PdfError(EvidenceError):
    """The PDF or its source cannot be used. The command exits 2, not 1."""


@dataclass(frozen=True)
class Extraction:
    """What a parser gets out of a PDF, and what the file holds besides text."""

    stream: str
    visual: str
    pages: int
    images: int


@dataclass(frozen=True)
class Recall:
    order: str
    words: int
    token: float
    header: float
    pair: float


@dataclass(frozen=True)
class PdfReport:
    findings: tuple[Finding, ...]
    recalls: tuple[Recall, ...]
    source_words: int
    pages: int
    images: int

    @property
    def ok(self) -> bool:
        return not self.findings


def words(text: str) -> list[str]:
    """Lower-case words: runs of letters and digits, after Unicode compatibility folding.

    The folding turns ligatures such as the single "fi" character into two letters, so a PDF
    that stores one still matches the source.
    """
    return _WORD.findall(unicodedata.normalize("NFKC", text).lower())


def source_words(markdown: str) -> list[str]:
    """The words a reader of the rendered resume would see: no evidence IDs, no link targets."""
    return words(_LINK.sub(r"\1", _EVIDENCE_TAG.sub(" ", markdown)))


def header_words(markdown: str) -> list[str]:
    """The words of the header block: every line before the first `## ` heading."""
    lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            break
        lines.append(line)
    return source_words("\n".join(lines))


def _grams(tokens: Sequence[str], size: int) -> Counter[tuple[str, ...]]:
    return Counter(tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1))


def recall(source: Sequence[str], got: Sequence[str], size: int) -> float:
    """The share of the source's word runs of length `size` that `got` also has, by count."""
    wanted = _grams(source, size)
    if not wanted:
        return 1.0
    have = _grams(got, size)
    return sum(min(count, have[gram]) for gram, count in wanted.items()) / sum(wanted.values())


def missing(source: Sequence[str], got: Sequence[str], limit: int = MISSING_SHOWN) -> list[str]:
    """The first distinct source words that `got` does not cover, in source order."""
    spare = Counter(got)
    found: list[str] = []
    for word in source:
        if spare[word] > 0:
            spare[word] -= 1
        elif word not in found:
            found.append(word)
            if len(found) == limit:
                break
    return found


def _percent(value: float) -> str:
    return f"{value:.1%}"


def check_pdf(source_markdown: str, extraction: Extraction) -> PdfReport:
    """Compare the resume with what its PDF gives back. Raises PdfError if there is no source."""
    source = source_words(source_markdown)
    if not source:
        raise PdfError("the source resume has no words to compare with")
    header = header_words(source_markdown)
    texts = ((STREAM, extraction.stream), (VISUAL, extraction.visual))
    got_by_order = [(order, words(text)) for order, text in texts]
    recalls = tuple(
        Recall(
            order,
            len(got),
            round(recall(source, got, 1), DIGITS),
            round(recall(header, got, 1), DIGITS),
            round(recall(source, got, 2), DIGITS),
        )
        for order, got in got_by_order
    )

    def report(found: list[Finding]) -> PdfReport:
        return PdfReport(tuple(found), recalls, len(source), extraction.pages, extraction.images)

    most_words = max(len(got) for _, got in got_by_order)
    if most_words < min(MIN_WORDS, len(source)):
        return report(
            [
                Finding(
                    "no-extractable-text",
                    0,
                    f"only {most_words} words can be read from {extraction.pages} page(s) with "
                    f"{extraction.images} image(s). An ATS would see an empty resume. Text has "
                    "to be in the file as text, not as pictures of text",
                )
            ]
        )
    problems: list[str] = []
    worst = min(recalls, key=lambda r: r.token)
    if worst.token < MIN_TOKEN_RECALL:
        gone = ", ".join(missing(source, dict(got_by_order)[worst.order]))
        problems.append(
            f"Only {_percent(worst.token)} of the resume's words come back as text in "
            f"{worst.order} (needs {_percent(MIN_TOKEN_RECALL)}). Missing, in resume order: {gone}"
        )
    worst_header = min(recalls, key=lambda r: r.header)
    if worst_header.header < MIN_HEADER_RECALL:
        gone = ", ".join(missing(header, dict(got_by_order)[worst_header.order]))
        problems.append(
            f"The name and contact lines do not all come back as text in {worst_header.order}. "
            f"Missing: {gone}"
        )
    if problems:
        if extraction.images:
            rule = "text-in-images"
            lead = f"{extraction.images} image(s) in the file, and text an ATS needs is missing. "
        else:
            rule = "low-token-recall"
            lead = ""
        return report([Finding(rule, 0, lead + " ".join(problems))])
    return report(
        [
            Finding(
                "reading-order-broken",
                0,
                f"in {item.order}, only {_percent(item.pair)} of the resume's word pairs stay "
                f"together (needs {_percent(MIN_PAIR_RECALL)}). {ORDER_ADVICE[item.order]}",
            )
            for item in recalls
            if item.pair < MIN_PAIR_RECALL
        ]
    )
