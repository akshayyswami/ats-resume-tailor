"""Parse an annotated resume into lines, with the evidence IDs each claim cites.

The format is deliberately rigid so the parse is deterministic. Before the first `## ` heading is
the header block (name, contact). After it, every non-blank line is a heading, a claim that ends in
`[E###, E###]`, or an item in the Skills section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

LineKind = Literal["header", "heading", "claim", "skills"]

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*?)\s*$")
_TRAILING_IDS = re.compile(r"\s*\[([^\]]*)\]\s*$")


@dataclass(frozen=True)
class Line:
    number: int
    raw: str
    kind: LineKind
    section: str  # lower-case text of the current `## ` heading, empty in the header block
    level: int  # heading level for headings, else 0
    body: str  # the text without the bullet marker and without the trailing ID list
    ids: tuple[str, ...]
    has_ids: bool  # a trailing `[...]` list with at least one entry


def _split_ids(text: str) -> tuple[str, tuple[str, ...]]:
    match = _TRAILING_IDS.search(text)
    if match is None:
        return text, ()
    ids = tuple(part.strip() for part in match.group(1).split(",") if part.strip())
    return text[: match.start()].rstrip(), ids


def strip_trailing_ids(raw: str) -> str:
    """The line without its trailing `[...]` list."""
    return _TRAILING_IDS.sub("", raw).rstrip()


def is_skills_section(section: str) -> bool:
    return section == "skills" or section.endswith(" skills")


def parse(text: str) -> list[Line]:
    lines: list[Line] = []
    section = ""
    in_header = True
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        heading = _HEADING.match(raw)
        if heading is not None:
            level = len(heading.group(1))
            if level == 2:
                in_header = False
                section = heading.group(2).strip().lower()
            kind: LineKind = "header" if in_header else "heading"
            lines.append(Line(number, raw, kind, section, level, heading.group(2), (), False))
            continue
        bullet = _BULLET.match(raw)
        content = bullet.group(1) if bullet is not None else raw.strip()
        if in_header:
            lines.append(Line(number, raw, "header", section, 0, content, (), False))
        elif is_skills_section(section):
            lines.append(Line(number, raw, "skills", section, 0, content, (), False))
        else:
            body, ids = _split_ids(content)
            lines.append(Line(number, raw, "claim", section, 0, body, ids, bool(ids)))
    return lines
