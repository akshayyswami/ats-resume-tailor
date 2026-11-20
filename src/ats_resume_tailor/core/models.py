"""The evidence bank: verified facts, the capability ledger, banned words and corrections.

Pure data. Reading YAML from disk happens in adapters/files.py.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LedgerStatus = Literal["claimable", "adjacent", "not_claimable"]
FactKind = Literal["role", "metric", "project", "skill"]


class EvidenceError(Exception):
    """The evidence bank cannot be used at all (bad schema, or duplicate IDs)."""


class _Model(BaseModel):
    # A typo in a YAML key must fail loudly, not be ignored.
    model_config = ConfigDict(extra="forbid", frozen=True)


class Verified(_Model):
    source: str
    date: date


class Fact(_Model):
    id: str = Field(pattern=r"^E\d{3,}$")
    kind: FactKind
    text: str
    skills: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    verified: Verified | None = None


class LedgerEntry(_Model):
    term: str
    status: LedgerStatus
    aliases: list[str] = Field(default_factory=list)
    # For an adjacent term: the one wording the resume may use, and the facts that justify it.
    say_instead: str | None = None
    supported_by: list[str] = Field(default_factory=list)


class Correction(_Model):
    wrong: str
    right: str


class Evidence(_Model):
    persona: str = ""
    facts: list[Fact]
    ledger: list[LedgerEntry] = Field(default_factory=list)
    banned_words: list[str] = Field(default_factory=list)
    corrections: list[Correction] = Field(default_factory=list)

    def duplicate_ids(self) -> list[str]:
        seen: set[str] = set()
        dupes: set[str] = set()
        for fact in self.facts:
            (dupes if fact.id in seen else seen).add(fact.id)
        return sorted(dupes)

    def fact_index(self) -> dict[str, Fact]:
        """Facts by ID. Refuses a bank with duplicate IDs, because a citation would be ambiguous."""
        dupes = self.duplicate_ids()
        if dupes:
            raise EvidenceError(f"duplicate fact IDs: {', '.join(dupes)}")
        return {fact.id: fact for fact in self.facts}
