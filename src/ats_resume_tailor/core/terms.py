"""The term lexicon: which skills and tools the checker knows about, and how to find them in text.

The lexicon is the ledger's terms and aliases plus every skill tag on a fact. A word that is in
none of those is not in the lexicon, and the checker says it did not check it.

Matching is on word boundaries. A surface form of one or two characters (`go`, `r`, `ci`) matches
only in capitalised or upper case (`Go`, `GO`), so ordinary words like "go live" are left alone.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ats_resume_tailor.core.models import Evidence, LedgerEntry

_SHORT = 2


def word_pattern(surface: str) -> re.Pattern[str]:
    """A pattern for `surface` as a whole word. Short surfaces match capitalised or upper only."""
    if len(surface) <= _SHORT:
        forms = sorted({surface.capitalize(), surface.upper()})
        body = "|".join(re.escape(form) for form in forms)
        return re.compile(rf"(?<![A-Za-z0-9])(?:{body})(?![A-Za-z0-9])")
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(surface)}(?![A-Za-z0-9])", re.IGNORECASE)


def normalise(text: str) -> str:
    """Lower case with whitespace collapsed, for comparing phrases."""
    return " ".join(text.lower().split())


@dataclass(frozen=True)
class Lexicon:
    patterns: tuple[tuple[str, re.Pattern[str]], ...]  # (canonical term, pattern), longest first
    ledger: dict[str, LedgerEntry]  # by canonical term
    alias_to_term: dict[str, str]

    def resolve(self, tag: str) -> str:
        """The canonical term for a tag or alias as written in the bank."""
        key = tag.strip().lower()
        return self.alias_to_term.get(key, key)

    def find(self, text: str) -> list[str]:
        """Canonical terms found in `text`, in order of first appearance, without repeats."""
        claimed: list[tuple[int, int]] = []
        hits: list[tuple[int, str]] = []
        for term, pattern in self.patterns:
            for match in pattern.finditer(text):
                span = (match.start(), match.end())
                if any(span[0] < end and start < span[1] for start, end in claimed):
                    continue  # inside a longer form already matched, e.g. "spark" in "apache spark"
                claimed.append(span)
                hits.append((span[0], term))
        found: list[str] = []
        for _, term in sorted(hits):
            if term not in found:
                found.append(term)
        return found


def build_lexicon(evidence: Evidence, extra_terms: Iterable[str] = ()) -> Lexicon:
    """The bank's terms, plus `extra_terms` such as the terms named in a gap file."""
    alias_to_term: dict[str, str] = {}
    ledger: dict[str, LedgerEntry] = {}
    for entry in evidence.ledger:
        term = entry.term.strip().lower()
        ledger[term] = entry
        alias_to_term[term] = term
        for alias in entry.aliases:
            alias_to_term[alias.strip().lower()] = term
    surfaces: dict[str, str] = dict(alias_to_term)
    for fact in evidence.facts:
        for tag in fact.skills:
            key = tag.strip().lower()
            surfaces.setdefault(key, alias_to_term.get(key, key))
    for extra in extra_terms:
        key = extra.strip().lower()
        if key:
            surfaces.setdefault(key, alias_to_term.get(key, key))
    ordered = sorted(surfaces.items(), key=lambda item: (-len(item[0]), item[0]))
    patterns = tuple((term, word_pattern(surface)) for surface, term in ordered)
    return Lexicon(patterns=patterns, ledger=ledger, alias_to_term=alias_to_term)
