from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from reportlab.pdfgen import canvas

from ats_resume_tailor.adapters.pdf import _count_images, read_pdf
from ats_resume_tailor.core.pdfcheck import PdfError, words

ROOT = Path(__file__).resolve().parents[2]
PDFS = ROOT / "evals" / "fixtures" / "pdfs"


class Node(dict[str, Any]):
    """A stand-in for a pypdf object: a dict that can resolve itself."""

    def get_object(self) -> Node:
        return self


def form(depth: int) -> Node:
    """A form XObject that holds one image and, while depth is above 0, another form."""
    inner: dict[str, Any] = {"/Im": Node({"/Subtype": "/Image"})}
    if depth:
        inner["/Fm"] = form(depth - 1)
    return Node({"/Subtype": "/Form", "/Resources": Node({"/XObject": Node(inner)})})


def test_a_single_column_pdf_gives_back_its_text_in_both_orders() -> None:
    got = read_pdf(PDFS / "one-column.pdf")
    assert (got.pages, got.images) == (1, 0)
    assert words(got.stream) == words(got.visual)
    assert words(got.stream)[:2] == ["jordan", "lee"]


def test_a_two_column_pdf_reads_differently_by_visual_line() -> None:
    got = read_pdf(PDFS / "two-column.pdf")
    assert sorted(words(got.stream)) == sorted(words(got.visual))
    assert words(got.stream) != words(got.visual)


def test_images_are_counted_and_a_picture_of_text_gives_no_text() -> None:
    assert read_pdf(PDFS / "one-column-with-logo.pdf").images == 1
    pictured = read_pdf(PDFS / "image-only.pdf")
    assert pictured.images == 1
    assert words(pictured.stream) == []
    assert read_pdf(PDFS / "blank.pdf").images == 0


def test_images_inside_form_objects_count_down_to_a_depth_limit() -> None:
    assert _count_images(None) == 0
    assert _count_images(Node({})) == 0
    assert _count_images(Node({"/XObject": Node({"/A": Node({"/Subtype": "/Image"})})})) == 1
    nested = Node({"/XObject": Node({"/F": form(1)})})
    assert _count_images(nested) == 2
    deep = Node({"/XObject": Node({"/F": form(10)})})
    assert _count_images(deep) == 3  # forms nested three deep are opened, the fourth is not


def test_a_file_that_is_not_a_pdf_is_an_input_error(tmp_path: Path) -> None:
    junk = tmp_path / "junk.pdf"
    junk.write_bytes(b"this is not a pdf at all")
    with pytest.raises(PdfError, match=r"cannot read .*junk\.pdf as a PDF"):
        read_pdf(junk)
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    with pytest.raises(PdfError, match="cannot read"):
        read_pdf(empty)


def test_a_missing_file_is_an_input_error(tmp_path: Path) -> None:
    with pytest.raises(PdfError, match=r"cannot read .*nope\.pdf"):
        read_pdf(tmp_path / "nope.pdf")


def test_an_encrypted_pdf_is_an_input_error_not_a_failure(tmp_path: Path) -> None:
    locked = tmp_path / "locked.pdf"
    pdf = canvas.Canvas(str(locked), encrypt="secret")
    pdf.drawString(72, 700, "Jordan Lee")
    pdf.save()
    with pytest.raises(PdfError, match="encrypted"):
        read_pdf(locked)
