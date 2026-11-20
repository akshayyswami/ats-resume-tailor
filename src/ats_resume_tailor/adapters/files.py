"""Read the evidence bank and resumes from disk."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from ats_resume_tailor.core.models import Evidence, EvidenceError


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvidenceError(f"cannot read {path}: {exc.strerror or exc}") from exc


def load_evidence(path: Path) -> Evidence:
    """Parse and validate a bank. Raises EvidenceError with a readable message on any problem."""
    try:
        data = yaml.safe_load(read_text(path))
    except yaml.YAMLError as exc:
        raise EvidenceError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise EvidenceError(f"{path} must be a YAML mapping with a `facts` list")
    try:
        return Evidence.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise EvidenceError(f"{path} does not match the evidence schema: {details}") from exc
