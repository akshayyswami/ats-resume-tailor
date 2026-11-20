from __future__ import annotations

from pathlib import Path

from ats_resume_tailor.core.export import strip_ids
from ats_resume_tailor.core.models import Evidence
from ats_resume_tailor.core.verify import verify


def test_strip_ids_removes_only_the_trailing_lists() -> None:
    text = (
        "# Name\n\n## Experience\n\n### Role [E001]\n\n"
        "- Did a thing. [E001, E002]\n- Also [x] this. [E003]\n"
    )
    assert strip_ids(text) == (
        "# Name\n\n## Experience\n\n### Role [E001]\n\n- Did a thing.\n- Also [x] this.\n"
    )


def test_strip_ids_leaves_skills_and_header_alone() -> None:
    text = "# Name [ok]\n\n## Skills\n\n- Python [x]\n"
    assert strip_ids(text) == text


def test_the_committed_clean_resume_is_the_export_of_the_sample(
    persona: Evidence, resume_path: Path
) -> None:
    annotated = resume_path.read_text(encoding="utf-8")
    assert verify(annotated, persona).ok
    clean = (resume_path.parent / "resume.clean.md").read_text(encoding="utf-8")
    assert strip_ids(annotated) == clean
    assert "[E" not in clean
