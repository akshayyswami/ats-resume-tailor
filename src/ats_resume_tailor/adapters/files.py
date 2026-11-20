"""Read the evidence bank and resumes from disk."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from ats_resume_tailor.core.gaps import GapError, GapTable, parse_gaps
from ats_resume_tailor.core.models import Evidence, EvidenceError

MAX_BYTES = 1_000_000
MAX_LINE = 10_000


def read_text(path: Path) -> str:
    """A resume, bank or gap file as text. Refuses what none of them would be.

    The limits keep one hostile line or file from making a regex run for minutes. A leading byte
    order mark is dropped, because an editor may add one.
    """
    try:
        if path.stat().st_size > MAX_BYTES:
            raise EvidenceError(f"{path} is larger than {MAX_BYTES:,} bytes")
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise EvidenceError(f"cannot read {path}: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"{path} is not valid UTF-8 text. Save it as UTF-8") from exc
    for number, line in enumerate(text.splitlines(), start=1):
        if len(line) > MAX_LINE:
            raise EvidenceError(f"{path}:{number} is longer than {MAX_LINE:,} characters")
    return text


def load_gaps(path: Path) -> GapTable:
    """Parse a gap file. Raises GapError, which is an EvidenceError, on a malformed table."""
    try:
        return parse_gaps(read_text(path))
    except GapError as exc:
        raise GapError(f"{path}: {exc}") from exc


def load_evidence(path: Path) -> Evidence:
    """Parse and validate a bank. Raises EvidenceError with a readable message on any problem."""
    try:
        data = yaml.safe_load(read_text(path))
    except (yaml.YAMLError, RecursionError) as exc:
        raise EvidenceError(f"{path} is not valid YAML: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise EvidenceError(f"{path} must be a YAML mapping with a `facts` list")
    try:
        return Evidence.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise EvidenceError(f"{path} does not match the evidence schema: {details}") from exc
