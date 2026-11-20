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
_MAX_OBJECTS = 10_000


def _count_images(resources: Any) -> int:
    """Image XObjects reachable from a page's resources, including inside form XObjects.

    Each object is visited once and the walk stops after _MAX_OBJECTS, so a file whose forms list
    each other many times cannot make it run for hours. Counting the objects avoids decoding them,
    which can fail on unusual image filters.
    """
    seen: set[Any] = set()
    pending: list[tuple[Any, int]] = [(resources, 0)]
    total = 0
    while pending and len(seen) < _MAX_OBJECTS:
        node, depth = pending.pop()
        if node is None or depth > _MAX_FORM_DEPTH:
            continue
        xobjects = node.get_object().get("/XObject")
        if xobjects is None:
            continue
        for reference in xobjects.get_object().values():
            key = (
                (reference.idnum, reference.generation)
                if hasattr(reference, "idnum")
                else id(reference)
            )
            if key in seen:
                continue
            seen.add(key)
            item = reference.get_object()
            subtype = item.get("/Subtype")
            if subtype == "/Image":
                total += 1
            elif subtype == "/Form":
                pending.append((item.get("/Resources"), depth + 1))
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
        # Only the type name: the message can carry text taken from the file.
        raise PdfError(f"cannot read {path} as a PDF ({type(exc).__name__})") from exc
    return Extraction(stream=stream, visual=visual, pages=len(pages), images=images)
