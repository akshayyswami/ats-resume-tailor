"""The gap file: one row per job requirement, marked HAVE, PARTIAL or MISSING.

    | Requirement | Status | Terms | Evidence |
    |---|---|---|---|
    | Production Kafka | PARTIAL | kafka | E004 |

    Lead: E004, because the posting is mostly about streaming.

The terms are what the checker watches for. Every term joins the lexicon, so a term no fact
supports fails when a bullet uses it, and a MISSING requirement's term fails anywhere. A malformed
file is an error, not a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from ats_resume_tailor.core.models import EvidenceError

STATUSES: Final = ("HAVE", "PARTIAL", "MISSING")
_HEADER = ("requirement", "status", "terms", "evidence")
_LEAD = re.compile(r"^\s*\**lead\**\s*:\s*(.+?)\s*$", re.IGNORECASE)
_SEPARATOR = re.compile(r"^[\s|:-]+$")


class GapError(EvidenceError):
    """The gap file cannot be used."""


@dataclass(frozen=True)
class GapRow:
    requirement: str
    status: str
    terms: tuple[str, ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class GapTable:
    rows: tuple[GapRow, ...]
    lead: str

    def terms(self) -> list[str]:
        return sorted({term for row in self.rows for term in row.terms})

    def missing_terms(self) -> set[str]:
        return {term for row in self.rows if row.status == "MISSING" for term in row.terms}


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _split(cell: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in cell.split(",") if part.strip())


def parse_gaps(text: str) -> GapTable:
    rows: list[GapRow] = []
    lead = ""
    header_seen = False
    for number, line in enumerate(text.splitlines(), start=1):
        match = _LEAD.match(line)
        if match is not None and not line.lstrip().startswith("|"):
            lead = match.group(1)
            continue
        if not line.lstrip().startswith("|"):
            continue
        if _SEPARATOR.match(line):
            continue
        cells = _cells(line)
        if not header_seen:
            if tuple(cell.lower() for cell in cells) != _HEADER:
                raise GapError(
                    f"line {number}: the table header must be "
                    "| Requirement | Status | Terms | Evidence |"
                )
            header_seen = True
            continue
        if len(cells) != len(_HEADER):
            raise GapError(f"line {number}: expected {len(_HEADER)} columns, found {len(cells)}")
        status = cells[1].upper()
        if status not in STATUSES:
            raise GapError(
                f"line {number}: status must be HAVE, PARTIAL or MISSING, not {cells[1]!r}"
            )
        terms = tuple(term.lower() for term in _split(cells[2]))
        rows.append(GapRow(cells[0], status, terms, _split(cells[3])))
    if not header_seen or not rows:
        raise GapError("no gap table found: expected | Requirement | Status | Terms | Evidence |")
    return GapTable(tuple(rows), lead)
