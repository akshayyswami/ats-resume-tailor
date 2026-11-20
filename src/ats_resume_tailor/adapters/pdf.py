"""Read a PDF with pypdf: its text in two reading orders, and how many images it holds.

This is the only module that imports pypdf. Every way a PDF can fail to open becomes a PdfError,
so the command can say "cannot use this input" and exit 2 instead of crashing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from ats_resume_tailor.core.pdfcheck import Extraction, PdfError

_MAX_FORM_DEPTH = 3
_ERROR_LENGTH = 200


def _count_images(resources: Any, depth: int = 0) -> int:
    """Image XObjects in a page's resources, including those inside form XObjects.

    Counting the objects avoids decoding them, which can fail on unusual image filters.
    """
    if resources is None or depth > _MAX_FORM_DEPTH:
        return 0
    xobjects = resources.get_object().get("/XObject")
    if xobjects is None:
        return 0
    total = 0
    for reference in xobjects.get_object().values():
        item = reference.get_object()
        subtype = item.get("/Subtype")
        if subtype == "/Image":
            total += 1
        elif subtype == "/Form":
            total += _count_images(item.get("/Resources"), depth + 1)
    return total


def read_pdf(path: Path) -> Extraction:
    """The PDF's text in drawing order and in visual line order, plus its page and image counts.

    Raises PdfError for a file that is missing, not a PDF, damaged or encrypted.
    """
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise PdfError(f"{path} is encrypted. Remove the password and check it again")
        pages = list(reader.pages)
        stream = "\n".join(page.extract_text(extraction_mode="plain") or "" for page in pages)
        visual = "\n".join(page.extract_text(extraction_mode="layout") or "" for page in pages)
        images = sum(_count_images(page.get("/Resources")) for page in pages)
    except PdfError:
        raise
    except OSError as exc:
        raise PdfError(f"cannot read {path}: {exc.strerror or exc}") from exc
    except Exception as exc:  # pypdf raises many types on damaged input
        detail = f"{type(exc).__name__}: {exc}"[:_ERROR_LENGTH]
        raise PdfError(f"cannot read {path} as a PDF ({detail})") from exc
    return Extraction(stream=stream, visual=visual, pages=len(pages), images=images)
