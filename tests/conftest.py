"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from ats_resume_tailor.adapters.files import load_evidence
from ats_resume_tailor.core.models import Evidence

ROOT = Path(__file__).resolve().parents[1]
PERSONA = ROOT / "examples" / "persona"


@pytest.fixture
def persona_path() -> Path:
    return PERSONA / "evidence.yaml"


@pytest.fixture
def resume_path() -> Path:
    return PERSONA / "resume.md"


@pytest.fixture
def persona() -> Evidence:
    return load_evidence(PERSONA / "evidence.yaml")


def resume_with(body: str) -> str:
    """A minimal resume around `body`, which goes under an Experience heading."""
    return f"# Jordan Lee\n\ncontact\n\n## Experience\n\n### Role, Co (2021 to 2024)\n\n{body}\n"
