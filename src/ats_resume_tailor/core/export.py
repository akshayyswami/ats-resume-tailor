"""Turn a verified, annotated resume into the clean text you send: the evidence IDs removed."""

from __future__ import annotations

from ats_resume_tailor.core.resume import parse, strip_trailing_ids


def strip_ids(text: str) -> str:
    """Remove the trailing `[E###, ...]` list from every claim line. Nothing else changes."""
    claims = {line.number for line in parse(text) if line.kind == "claim" and line.has_ids}
    out = [
        strip_trailing_ids(raw) if number in claims else raw
        for number, raw in enumerate(text.splitlines(), start=1)
    ]
    return "\n".join(out) + "\n"
