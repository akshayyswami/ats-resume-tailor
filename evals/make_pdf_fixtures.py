"""Render the invented persona's resume as the PDFs the pdf-check planted faults use.

    uv run python evals/make_pdf_fixtures.py

Writes evals/fixtures/pdfs/. The PDFs are committed. Regenerating them is a manual step, and no
test compares bytes, so a library upgrade cannot cause noise. reportlab is a development
dependency only.

Every file is the text of examples/persona/resume.clean.md, drawn one way:

  one-column            plain single column. Must pass.
  one-column-with-logo  the same with a small decorative image. Must pass: an image alone is fine.
  two-column            left column drawn first, then the right. Clean in drawing order,
                        interleaved when read by visual line.
  stream-scrambled      a clean single column that was drawn bottom to top. It looks right and
                        reads in reverse for a parser that follows drawing order.
  image-header          the name and contact lines are a picture. The rest is text.
  image-section         the second job and the Skills list are a picture. The rest is text.
  image-only            the whole resume is one picture of text. No text at all.
  blank                 an empty page.
  half-resume           only the first half of the resume. The rest is missing.
"""

from __future__ import annotations

import io
import textwrap
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    PageTemplate,
    Paragraph,
)
from reportlab.platypus import (
    Image as ImageFlowable,
)

EVALS = Path(__file__).resolve().parent
SOURCE = EVALS.parent / "examples" / "persona" / "resume.clean.md"
OUT = EVALS / "fixtures" / "pdfs"
PAGE_W, PAGE_H = A4
MARGIN = 50

_styles = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=_styles["BodyText"], fontSize=10, leading=13)
H1 = ParagraphStyle("h1", parent=_styles["Heading1"], fontSize=18)
H2 = ParagraphStyle("h2", parent=_styles["Heading2"], fontSize=13)
H3 = ParagraphStyle("h3", parent=_styles["Heading3"], fontSize=11)


def flowables(markdown: str) -> list[Any]:
    """The resume's lines as paragraphs: headings, bullets and plain lines."""
    items: list[Any] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            items.append(Paragraph(escape(line[4:]), H3))
        elif line.startswith("## "):
            items.append(Paragraph(escape(line[3:]), H2))
        elif line.startswith("# "):
            items.append(Paragraph(escape(line[2:]), H1))
        elif line.startswith("- "):
            items.append(Paragraph("&bull; " + escape(line[2:]), BODY))
        else:
            items.append(Paragraph(escape(line), BODY))
    return items


def _png(width: int, height: int, draw: Any) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    draw(ImageDraw.Draw(image))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _text_image(lines: list[str], size: int) -> Image.Image:
    font = ImageFont.load_default(size)
    step = size + 6
    image = Image.new("RGB", (900, step * (len(lines) + 1)), "white")
    pen = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        pen.text((6, 6 + index * step), line, fill="black", font=font)
    return image


def one_column(path: Path, markdown: str, logo: bool = False) -> None:
    doc = BaseDocTemplate(str(path), pagesize=A4, invariant=1)

    def draw_logo(pdf: Any, _doc: Any) -> None:
        mark = _png(64, 64, lambda pen: pen.ellipse((6, 6, 58, 58), fill="#2a5db0"))
        pdf.drawImage(ImageReader(io.BytesIO(mark)), PAGE_W - 110, PAGE_H - 90, 40, 40)

    frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN)

    def nothing(_pdf: Any, _doc: Any) -> None:
        return None

    page = PageTemplate(id="p", frames=[frame], onPage=draw_logo if logo else nothing)
    doc.addPageTemplates([page])
    doc.build(flowables(markdown))


def two_column(path: Path, markdown: str) -> None:
    doc = BaseDocTemplate(str(path), pagesize=A4, invariant=1)
    gap = 20
    width = (PAGE_W - 2 * MARGIN - gap) / 2
    height = PAGE_H - 2 * MARGIN
    frames = [
        Frame(MARGIN, MARGIN, width, height, id="left"),
        Frame(MARGIN + width + gap, MARGIN, width, height, id="right"),
    ]
    doc.addPageTemplates([PageTemplate(id="p", frames=frames)])
    items = flowables(markdown)
    half = len(items) // 2
    doc.build([*items[:half], FrameBreak(), *items[half:]])


def stream_scrambled(path: Path, markdown: str) -> None:
    """One column, every line in its right place, drawn from the last line to the first."""
    rows: list[tuple[str, str, int]] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            rows.append((line[2:], "Helvetica-Bold", 16))
        elif line.startswith("## "):
            rows.append((line[3:], "Helvetica-Bold", 13))
        elif line.startswith("### "):
            rows.append((line[4:], "Helvetica-Bold", 11))
        else:
            text = "\u2022 " + line[2:] if line.startswith("- ") else line
            rows.extend((part, "Helvetica", 10) for part in textwrap.wrap(text, 100))
    placed: list[tuple[str, str, int, float]] = []
    y = PAGE_H - MARGIN
    for text, font, size in rows:
        y -= size + 4
        placed.append((text, font, size, y))
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    for text, font, size, height in reversed(placed):
        pdf.setFont(font, size)
        pdf.drawString(MARGIN, height, text)
    pdf.save()


def image_header(path: Path, markdown: str) -> None:
    """The first two non-empty lines (name, contact) as a picture; the rest as wrapped text."""
    lines = [line for line in markdown.splitlines() if line.strip()]
    picture = _text_image([line.lstrip("# ").strip() for line in lines[:2]], 20)
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    buffer.seek(0)
    scale = 0.55
    head = ImageFlowable(buffer, width=picture.width * scale, height=picture.height * scale)
    head.hAlign = "LEFT"
    doc = BaseDocTemplate(str(path), pagesize=A4, invariant=1)
    frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])
    doc.build([head, *flowables("\n".join(lines[2:]))])


def image_section(path: Path, markdown: str) -> None:
    """Everything from the second job heading on, as a picture; the rest as wrapped text."""
    lines = markdown.splitlines()
    cut = [i for i, line in enumerate(lines) if line.startswith("### ")][1]
    rows: list[str] = []
    for line in lines[cut:]:
        rows.extend(textwrap.wrap(line.lstrip("#- ").strip(), 95) or [""])
    picture = _text_image(rows, 14)
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    buffer.seek(0)
    scale = (PAGE_W - 2 * MARGIN) / picture.width
    tail = ImageFlowable(buffer, width=picture.width * scale, height=picture.height * scale)
    tail.hAlign = "LEFT"
    doc = BaseDocTemplate(str(path), pagesize=A4, invariant=1)
    frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])
    doc.build([*flowables("\n".join(lines[:cut])), tail])


def image_only(path: Path, markdown: str) -> None:
    rows: list[str] = []
    for line in markdown.splitlines():
        text = line.lstrip("#- ").strip()
        rows.extend(textwrap.wrap(text, 95) or [""])
    picture = _text_image(rows, 12)
    scale = min((PAGE_W - 2 * MARGIN) / picture.width, (PAGE_H - 2 * MARGIN) / picture.height)
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    width, height = picture.width * scale, picture.height * scale
    pdf.drawImage(ImageReader(picture), MARGIN, PAGE_H - MARGIN - height, width, height)
    pdf.save()


def blank(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    pdf.showPage()
    pdf.save()


def main() -> int:
    markdown = SOURCE.read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    lines = markdown.splitlines()
    one_column(OUT / "one-column.pdf", markdown)
    one_column(OUT / "one-column-with-logo.pdf", markdown, logo=True)
    two_column(OUT / "two-column.pdf", markdown)
    stream_scrambled(OUT / "stream-scrambled.pdf", markdown)
    image_header(OUT / "image-header.pdf", markdown)
    image_section(OUT / "image-section.pdf", markdown)
    image_only(OUT / "image-only.pdf", markdown)
    blank(OUT / "blank.pdf")
    one_column(OUT / "half-resume.pdf", "\n".join(lines[: len(lines) // 2]))
    for path in sorted(OUT.glob("*.pdf")):
        print(f"{path.relative_to(EVALS.parent)}  {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
