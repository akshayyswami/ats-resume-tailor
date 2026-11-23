"""The checks. `verify` runs an annotated resume against the evidence bank. `check_evidence`
runs the bank against itself.

Two outcomes, never blended. FAIL means a rule broke. NOT_CHECKED means the tool could not verify
something and says so. It never guesses and never passes what it could not check as if it had.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final, Literal

from ats_resume_tailor.core.ai_tells import AI_TELLS
from ats_resume_tailor.core.gaps import GapTable
from ats_resume_tailor.core.models import Evidence, Fact
from ats_resume_tailor.core.numbers import NumberMention, canonical_values, extract, quantity_words
from ats_resume_tailor.core.resume import Line, parse
from ats_resume_tailor.core.template import PLACEHOLDER_SOURCE, PLACEHOLDER_TEXT
from ats_resume_tailor.core.terms import Lexicon, build_lexicon, normalise, word_pattern

Status = Literal["FAIL", "NOT_CHECKED"]

# Every rule below must have a planted fault in evals/faults.yaml. measure.py fails if one does not.
RESUME_RULES: Final = (
    "no-evidence-id",
    "unknown-evidence-id",
    "unverified-evidence-cited",
    "number-not-in-cited-evidence",
    "number-from-other-fact",
    "not-claimable-term",
    "adjacent-term-overclaim",
    "term-not-in-cited-evidence",
    "unsupported-skill",
    "known-wrong-claim",
    "missing-requirement-claimed",
    "banned-word",
    "em-dash",
    "claim-in-header",
    "no-claims",
    "hidden-characters",
)
BANK_RULES: Final = (
    "duplicate-id",
    "missing-verified",
    "metric-without-number",
    "claimable-without-evidence",
    "adjacent-incomplete",
    "placeholder-fact",
)
ALL_RULES: Final = RESUME_RULES + BANK_RULES

_EM_DASH = "—"
_LABEL = re.compile(r"^[^,;:]*:\s*")


@dataclass(frozen=True)
class Finding:
    rule: str
    line: int  # 0 when the finding is about the evidence bank, not a resume line
    message: str
    status: Status = "FAIL"


@dataclass(frozen=True)
class Report:
    findings: tuple[Finding, ...]
    claim_lines: int
    skill_items: int
    unchecked_headings: int

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.status == "FAIL"]

    @property
    def not_checked(self) -> list[Finding]:
        return [f for f in self.findings if f.status == "NOT_CHECKED"]

    @property
    def ok(self) -> bool:
        return not self.failures


def _fact_numbers(fact: Fact) -> set[str]:
    values = canonical_values(fact.text)
    for raw in fact.numbers:
        values |= canonical_values(raw)
    return values


def _resolved_tags(fact: Fact, lexicon: Lexicon) -> set[str]:
    return {lexicon.resolve(tag) for tag in fact.skills}


def _banned_patterns(evidence: Evidence) -> list[tuple[str, re.Pattern[str]]]:
    words = sorted({w.strip().lower() for w in (*AI_TELLS, *evidence.banned_words) if w.strip()})
    return [
        (word, re.compile(rf"(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])", re.IGNORECASE))
        for word in words
    ]


_BULLET_START = re.compile(r"^\s*[-*+]\s+")
# A contact detail: an email, a link, or a phone-like run of digits.
_CONTACT = re.compile(r"@|https?://|www\.|\d[\d\s().-]{5,}\d")
_YEARS = re.compile(r"\d\+?\s*(?:years?|yrs?|months?)\b", re.IGNORECASE)
HEADER_PROSE_WORDS: Final = 9


def _claim_shaped(mention: NumberMention) -> bool:
    """A figure that states a result, not a phone number: a percent, multiplier, amount or k/m/b."""
    raw = mention.raw
    return mention.value.endswith(("%", "x")) or raw[0] in "$\u00a3\u20ac" or raw[-1] in "kKmMbB"


def _header_findings(line: Line, lexicon: Lexicon) -> list[Finding]:
    """The header block holds a name and contact details. Anything shaped like a claim fails there.

    Nothing in the header cites evidence, so a claim placed in it would never be checked.
    """
    if line.level == 1:
        return []  # the name
    found: list[Finding] = []
    if line.level >= 3 or _BULLET_START.match(line.raw):
        found.append(
            Finding(
                "claim-in-header",
                line.number,
                "a bullet or sub-heading before the first `## ` section cites no evidence and is "
                "never checked. Put it under a `## ` section",
            )
        )
    terms = lexicon.find(line.body)
    if terms:
        found.append(
            Finding(
                "claim-in-header",
                line.number,
                f'"{terms[0]}" appears in the header block, which is never checked. Put it in a '
                "bullet under a `## ` section with evidence IDs",
            )
        )
    figures = [m.raw for m in extract(line.raw) if _claim_shaped(m)]
    years = _YEARS.search(line.raw)
    if years:
        figures.append(years.group(0))
    if figures:
        found.append(
            Finding(
                "claim-in-header",
                line.number,
                f'the figure "{figures[0]}" appears in the header block, which is never checked. '
                "Put it in a bullet under a `## ` section with evidence IDs",
            )
        )
    if not found and len(line.body.split()) >= HEADER_PROSE_WORDS and not _CONTACT.search(line.raw):
        found.append(
            Finding(
                "header-prose",
                line.number,
                "a long line in the header block is not checked",
                "NOT_CHECKED",
            )
        )
    return found


def _hidden_characters(text: str) -> list[Finding]:
    """Invisible format characters: zero-width spaces, soft hyphens, bidi marks."""
    found: list[Finding] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        hidden = [ch for ch in raw if unicodedata.category(ch) == "Cf"]
        if hidden:
            ch = hidden[0]
            name = unicodedata.name(ch, "FORMAT CHARACTER")
            found.append(
                Finding(
                    "hidden-characters",
                    number,
                    f"contains an invisible character (U+{ord(ch):04X} {name}). It hides text "
                    "from a reader and splits a word for a checker",
                )
            )
    return found


def _fold(text: str) -> str:
    """Compatibility-fold the text and drop format characters, so a lookalike cannot dodge a term.

    Fullwidth letters become plain ones. The invisible characters were already reported.
    """
    folded = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")


def _style_findings(
    line: Line, banned: list[tuple[str, re.Pattern[str]]], evidence: Evidence
) -> list[Finding]:
    found: list[Finding] = []
    if _EM_DASH in line.raw:
        found.append(Finding("em-dash", line.number, "contains an em dash"))
    for word, pattern in banned:
        if pattern.search(line.raw):
            found.append(Finding("banned-word", line.number, f'uses the banned word "{word}"'))
    text = normalise(line.raw)
    for correction in evidence.corrections:
        if correction.wrong.strip() and normalise(correction.wrong) in text:
            found.append(
                Finding(
                    "known-wrong-claim",
                    line.number,
                    f'repeats a corrected claim: "{correction.wrong}". Use: {correction.right}',
                )
            )
    return found


def _term_findings(
    line: Line, terms: list[str], cited: list[Fact], lexicon: Lexicon
) -> list[Finding]:
    found: list[Finding] = []
    cited_tags: set[str] = set()
    for fact in cited:
        cited_tags |= _resolved_tags(fact, lexicon)
    cited_ids = {fact.id for fact in cited}
    # A term the cited fact itself says is supported, whether or not it is a tag on the fact.
    cited_said = {term for fact in cited for term in lexicon.find(fact.text)}
    for term in terms:
        entry = lexicon.ledger.get(term)
        if entry is not None and entry.status == "not_claimable":
            found.append(
                Finding("not-claimable-term", line.number, f'"{term}" is marked not claimable')
            )
        elif entry is not None and entry.status == "adjacent":
            sanctioned = bool(entry.say_instead) and normalise(
                entry.say_instead or ""
            ) in normalise(line.body)
            supported = bool(cited_ids & set(entry.supported_by))
            if not (sanctioned and supported):
                found.append(
                    Finding(
                        "adjacent-term-overclaim",
                        line.number,
                        f'"{term}" is adjacent only. Use exactly: {entry.say_instead}, '
                        f"citing {', '.join(entry.supported_by) or 'a supporting fact'}",
                    )
                )
        elif term not in cited_tags and term not in cited_said:
            found.append(
                Finding(
                    "term-not-in-cited-evidence",
                    line.number,
                    f'"{term}" is not a skill of the facts this line cites',
                )
            )
    return found


def _claim_findings(
    line: Line, index: dict[str, Fact], lexicon: Lexicon, evidence: Evidence
) -> list[Finding]:
    if not line.has_ids:
        return [
            Finding("no-evidence-id", line.number, "claim has no evidence ID: end it with [E###]")
        ]
    found: list[Finding] = []
    cited: list[Fact] = []
    for fact_id in line.ids:
        fact = index.get(fact_id)
        if fact is None:
            found.append(
                Finding("unknown-evidence-id", line.number, f"{fact_id} is not in the bank")
            )
        elif fact.verified is None:
            found.append(
                Finding(
                    "unverified-evidence-cited", line.number, f"{fact_id} is not marked verified"
                )
            )
        else:
            cited.append(fact)
            if _is_placeholder(fact):
                found.append(
                    Finding(
                        "placeholder-fact",
                        line.number,
                        f"{fact_id} is the template's example fact, not one you verified",
                    )
                )
    if not cited:
        return found
    supported: set[str] = set()
    for fact in cited:
        supported |= _fact_numbers(fact)
    elsewhere: set[str] = set()
    for fact in evidence.facts:
        if fact not in cited:
            elsewhere |= _fact_numbers(fact)
    mentions = extract(line.body)
    for mention in mentions:
        if mention.value in supported:
            continue
        rule = (
            "number-from-other-fact"
            if mention.value in elsewhere
            else ("number-not-in-cited-evidence")
        )
        where = (
            "only in a fact this line does not cite"
            if rule == "number-from-other-fact"
            else ("in none of the cited facts")
        )
        found.append(Finding(rule, line.number, f'"{mention.raw}" appears {where}'))
    terms = lexicon.find(line.body)
    found.extend(_term_findings(line, terms, cited, lexicon))
    cited_text = " ".join(fact.text for fact in cited).lower()
    for word in quantity_words(line.body):
        if word not in cited_text:
            found.append(
                Finding(
                    "quantity-word",
                    line.number,
                    f'"{word}" states a quantity with no digit, so it was not checked',
                    "NOT_CHECKED",
                )
            )
    if not mentions and not terms:
        found.append(
            Finding(
                "weakly-checked",
                line.number,
                "no number or known term to check; only the cited facts were checked",
                "NOT_CHECKED",
            )
        )
    return found


def _skill_findings(line: Line, lexicon: Lexicon, bank_tags: set[str]) -> list[Finding]:
    found: list[Finding] = []
    content = _LABEL.sub("", line.body)
    for item in (part.strip() for part in re.split(r"[,;]", content)):
        if not item:
            continue
        terms = lexicon.find(item)
        if not terms:
            found.append(
                Finding("unsupported-skill", line.number, f'"{item}" is not in the evidence bank')
            )
        for term in terms:
            entry = lexicon.ledger.get(term)
            if entry is not None and entry.status == "not_claimable":
                found.append(
                    Finding("not-claimable-term", line.number, f'"{term}" is marked not claimable')
                )
            elif entry is not None and entry.status == "adjacent":
                found.append(
                    Finding(
                        "adjacent-term-overclaim",
                        line.number,
                        f'"{term}" is adjacent only and cannot stand alone in a skills list',
                    )
                )
            elif term not in bank_tags:
                found.append(
                    Finding(
                        "unsupported-skill",
                        line.number,
                        f'"{term}" is not a skill of any verified fact',
                    )
                )
    return found


def verify(text: str, evidence: Evidence, gaps: GapTable | None = None) -> Report:
    """Check an annotated resume against the bank. Raises EvidenceError on duplicate IDs.

    With a gap table, its terms join the lexicon, so a term no cited fact supports fails when a
    bullet uses it, and a term of a MISSING requirement fails anywhere after the header block.
    The header block is the name and contact details: a skill, a claim-shaped figure, a bullet or
    a sub-heading there fails, and a resume with no claim lines at all fails.
    """
    index = evidence.fact_index()
    lexicon = build_lexicon(evidence, gaps.terms() if gaps is not None else ())
    missing = (
        {lexicon.resolve(term) for term in gaps.missing_terms()} if gaps is not None else set()
    )
    banned = _banned_patterns(evidence)
    bank_tags: set[str] = set()
    for fact in evidence.facts:
        # The template's example fact has `python` among its skills, and nobody verified it, so
        # it must not back a Skills list any more than it may back a bullet.
        if fact.verified is not None and not _is_placeholder(fact):
            bank_tags |= _resolved_tags(fact, lexicon)
    findings: list[Finding] = _hidden_characters(text)
    claim_lines = skill_items = unchecked_headings = 0
    for line in parse(_fold(text)):
        findings.extend(_style_findings(line, banned, evidence))
        if line.kind == "header":
            findings.extend(_header_findings(line, lexicon))
            continue
        for term in lexicon.find(line.body):
            if term in missing:
                findings.append(
                    Finding(
                        "missing-requirement-claimed",
                        line.number,
                        f'"{term}" is marked MISSING in the gap file but appears here',
                    )
                )
        # A not-claimable term fails anywhere after the header block, headings included.
        if line.kind == "heading":
            unchecked_headings += 1 if line.level >= 3 else 0
            for term in lexicon.find(line.body):
                entry = lexicon.ledger.get(term)
                if entry is not None and entry.status == "not_claimable":
                    findings.append(
                        Finding(
                            "not-claimable-term", line.number, f'"{term}" is marked not claimable'
                        )
                    )
        elif line.kind == "skills":
            skill_items += 1
            findings.extend(_skill_findings(line, lexicon, bank_tags))
        else:
            claim_lines += 1
            findings.extend(_claim_findings(line, index, lexicon, evidence))
    if claim_lines == 0 and skill_items == 0:
        findings.append(
            Finding(
                "no-claims",
                0,
                "the resume has no claim lines and no skills items, so nothing was checked. "
                "Claims go in bullets under `## ` sections, each ending in evidence IDs",
            )
        )
    return Report(tuple(findings), claim_lines, skill_items, unchecked_headings)


def _is_placeholder(fact: Fact) -> bool:
    """True while a fact still carries the text or the source that `init` wrote."""
    if PLACEHOLDER_TEXT.lower() in fact.text.lower():
        return True
    return fact.verified is not None and PLACEHOLDER_SOURCE.lower() in fact.verified.source.lower()


def check_evidence(evidence: Evidence) -> list[Finding]:
    """Check the bank itself. Findings carry line 0."""
    found: list[Finding] = []
    for fact_id in evidence.duplicate_ids():
        found.append(Finding("duplicate-id", 0, f"{fact_id} is used by more than one fact"))
    lexicon = build_lexicon(evidence)
    ids = {fact.id for fact in evidence.facts}
    verified_tags: set[str] = set()
    for fact in evidence.facts:
        if _is_placeholder(fact):
            found.append(
                Finding(
                    "placeholder-fact",
                    0,
                    f"{fact.id} is still the template's example: replace its text, source and "
                    "date with a fact you can back up",
                )
            )
        if fact.verified is None or not fact.verified.source.strip():
            found.append(
                Finding("missing-verified", 0, f"{fact.id} has no verification source and date")
            )
        else:
            verified_tags |= _resolved_tags(fact, lexicon)
        if fact.kind == "metric" and not _fact_numbers(fact):
            found.append(
                Finding("metric-without-number", 0, f"{fact.id} is a metric with no number")
            )
    for entry in evidence.ledger:
        term = entry.term.strip().lower()
        if entry.status == "claimable" and term not in verified_tags:
            found.append(
                Finding(
                    "claimable-without-evidence",
                    0,
                    f'"{term}" is claimable but no verified fact lists it as a skill',
                )
            )
        if entry.status == "adjacent":
            forms = [term, *(alias.strip().lower() for alias in entry.aliases)]
            phrase = normalise(entry.say_instead or "")
            problems = []
            if not phrase:
                problems.append("no say_instead wording")
            elif not any(word_pattern(form).search(phrase) for form in forms):
                problems.append("say_instead does not contain the term")
            if not entry.supported_by:
                problems.append("no supported_by facts")
            unknown = [fact_id for fact_id in entry.supported_by if fact_id not in ids]
            if unknown:
                problems.append(f"supported_by names unknown facts: {', '.join(unknown)}")
            if problems:
                found.append(Finding("adjacent-incomplete", 0, f'"{term}": {"; ".join(problems)}'))
    return found
