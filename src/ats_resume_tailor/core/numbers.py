"""Find numbers in text and reduce each to one canonical string, so "1,200" matches "1200".

Canonical form: plain decimal digits, then `%` for percentages and `x` for multipliers.
`40%`, `40 percent` and `40 per cent` all become `40%`. `$1.2M` becomes `1200000`.
Currency symbols are dropped. A number glued to a letter (`p95`, `EC2`) is a label, not a figure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

_NUMBER = re.compile(
    r"(?<![\w.])[$£€]?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<unit>%|\s?percent\b|\s?per cent\b|[kKmMbB]\b|\s?x\b|\u00d7)?"
)
_MULTIPLIER = {"k": Decimal(1000), "m": Decimal(1_000_000), "b": Decimal(1_000_000_000)}

# Words that state a quantity without a digit. They cannot be checked against a fact's numbers,
# so verify reports them as not checked unless a cited fact uses the same word.
QUANTITY_WORDS = (
    "doubled",
    "tripled",
    "quadrupled",
    "halved",
    "twice",
    "thrice",
    "dozens",
    "hundreds",
    "thousands",
    "millions",
    "billions",
)
_QUANTITY = re.compile(r"\b(" + "|".join(QUANTITY_WORDS) + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class NumberMention:
    raw: str
    value: str


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


def extract(text: str) -> list[NumberMention]:
    """Every figure in `text`, in order, each with its canonical value."""
    found: list[NumberMention] = []
    for match in _NUMBER.finditer(text):
        value = Decimal(match.group("num").replace(",", ""))
        unit = (match.group("unit") or "").strip().lower()
        if unit in _MULTIPLIER:
            canonical = _plain(value * _MULTIPLIER[unit])
        elif unit in ("%", "percent", "per cent"):
            canonical = _plain(value) + "%"
        elif unit in ("x", "\u00d7"):
            canonical = _plain(value) + "x"
        else:
            canonical = _plain(value)
        found.append(NumberMention(raw=match.group(0).strip(), value=canonical))
    return found


def canonical_values(text: str) -> set[str]:
    return {mention.value for mention in extract(text)}


def quantity_words(text: str) -> list[str]:
    return [m.group(1).lower() for m in _QUANTITY.finditer(text)]
