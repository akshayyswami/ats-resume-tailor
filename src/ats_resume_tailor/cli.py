"""Command line interface. Thin: parse arguments, call core, print.

Exit codes: 0 clean, 1 a check failed, 2 the input could not be used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ats_resume_tailor import __version__
from ats_resume_tailor.adapters.files import load_evidence, load_gaps, read_text
from ats_resume_tailor.adapters.pdf import read_pdf
from ats_resume_tailor.core.export import strip_ids
from ats_resume_tailor.core.gaps import GapTable
from ats_resume_tailor.core.models import EvidenceError
from ats_resume_tailor.core.pdfcheck import (
    MIN_HEADER_RECALL,
    MIN_PAIR_RECALL,
    MIN_TOKEN_RECALL,
    PdfReport,
    check_pdf,
)
from ats_resume_tailor.core.template import EVIDENCE_TEMPLATE
from ats_resume_tailor.core.verify import Finding, Report, check_evidence, verify

app = typer.Typer(
    help="Check that every line of a resume traces to evidence you verified.",
    no_args_is_help=True,
)

EvidenceOption = Annotated[
    Path, typer.Option("--evidence", "-e", help="Path to your evidence.yaml.")
]
GapsOption = Annotated[
    Path | None,
    typer.Option("--gaps", "-g", help="Path to the gap file for this job description."),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Print machine-readable JSON.")]
SourceOption = Annotated[
    Path,
    typer.Option("--source", "-s", help="The exported clean resume the PDF was made from."),
]


def _as_dict(finding: Finding) -> dict[str, object]:
    return {
        "rule": finding.rule,
        "line": finding.line,
        "status": finding.status,
        "message": finding.message,
    }


def _clean(text: str) -> str:
    """The text with every non-printable character shown as an escape.

    A finding can quote the resume, and a resume can hold terminal control sequences.
    """
    return "".join(ch if ch.isprintable() or ch == "\t" else f"\\u{ord(ch):04x}" for ch in text)


def _show(label: str, finding: Finding) -> None:
    where = f"{label}:{finding.line}" if finding.line else label
    status = finding.status.replace("_", " ")
    typer.echo(f"{_clean(where)}: {status} {finding.rule}: {_clean(finding.message)}")


def _summary(report: Report) -> str:
    verdict = "ok" if report.ok else "FAIL"
    return (
        f"verify: {verdict}. {len(report.failures)} fail, {len(report.not_checked)} not "
        f"checked, {report.claim_lines} claim lines, {report.skill_items} skill lines, "
        f"{report.unchecked_headings} heading lines not checked"
    )


def _run_verify(resume: Path, evidence: Path, gaps: Path | None) -> tuple[str, Report]:
    """Read the inputs and verify. Exits 2, with a message, if an input cannot be used."""
    try:
        text = read_text(resume)
        table: GapTable | None = load_gaps(gaps) if gaps is not None else None
        return text, verify(text, load_evidence(evidence), table)
    except EvidenceError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.callback()
def main() -> None:
    """ats-resume-tailor command line."""


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@app.command()
def init(path: Annotated[Path, typer.Argument()] = Path("evidence.yaml")) -> None:
    """Write a starter evidence bank. Never overwrites an existing file."""
    try:
        with path.open("x", encoding="utf-8") as handle:  # fails on a file or a dangling symlink
            handle.write(EVIDENCE_TEMPLATE)
    except FileExistsError as exc:
        typer.echo(f"{path} already exists; not overwriting it", err=True)
        raise typer.Exit(1) from exc
    except OSError as exc:
        typer.echo(f"error: cannot write {path}: {exc.strerror or exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(
        f"wrote {path}. Replace the example fact, then run: check-evidence {path}. "
        "It fails until you do."
    )


@app.command("check-evidence")
def check_evidence_command(path: Path, json_output: JsonOption = False) -> None:
    """Check an evidence bank: unique IDs, every fact verified, metrics carry numbers."""
    try:
        findings = check_evidence(load_evidence(path))
    except EvidenceError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps({"ok": not findings, "findings": [_as_dict(f) for f in findings]}))
    else:
        for finding in findings:
            _show(str(path), finding)
        typer.echo(f"check-evidence: {'ok' if not findings else f'{len(findings)} fail'}")
    raise typer.Exit(1 if findings else 0)


@app.command("verify")
def verify_command(
    resume: Path,
    evidence: EvidenceOption,
    gaps: GapsOption = None,
    json_output: JsonOption = False,
) -> None:
    """Check an annotated resume against the evidence bank."""
    _, report = _run_verify(resume, evidence, gaps)
    if json_output:
        payload = {
            "ok": report.ok,
            "claim_lines": report.claim_lines,
            "skill_items": report.skill_items,
            "unchecked_headings": report.unchecked_headings,
            "findings": [_as_dict(f) for f in report.findings],
        }
        typer.echo(json.dumps(payload))
    else:
        for finding in report.findings:
            _show(str(resume), finding)
        typer.echo(_summary(report))
    raise typer.Exit(0 if report.ok else 1)


EXPORT_SUFFIXES = (".md", ".markdown", ".txt")


def _export_problem(target: Path, protected: dict[str, Path | None]) -> str:
    """Why `export` must not write to `target`, or an empty string.

    The output is text the user asked for, so it may go to a new or old text file and nowhere
    else: not over the files the check read, not through a link, not to a path with another type.
    """
    if target.suffix.lower() not in EXPORT_SUFFIXES:
        return f"the output must be a {', '.join(EXPORT_SUFFIXES)} file, not {target.name}"
    if target.is_symlink():
        return f"{target} is a symbolic link, and export does not write through links"
    for label, path in protected.items():
        if path is not None and target.resolve() == path.resolve():
            return f"the output would overwrite the {label}"
    return ""


@app.command("export")
def export_command(
    resume: Path,
    evidence: EvidenceOption,
    gaps: GapsOption = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Where to write it. Default: <resume>.clean.md"),
    ] = None,
) -> None:
    """Write the resume without its evidence IDs. Writes nothing if verify fails."""
    text, report = _run_verify(resume, evidence, gaps)
    for finding in report.findings:
        _show(str(resume), finding)
    if not report.ok:
        typer.echo(f"{_summary(report)}\nexport: refused, nothing written", err=True)
        raise typer.Exit(1)
    target = output or resume.with_name(f"{resume.stem}.clean{resume.suffix}")
    problem = _export_problem(
        target, {"annotated resume": resume, "evidence file": evidence, "gap file": gaps}
    )
    if problem:
        typer.echo(f"error: {problem}", err=True)
        raise typer.Exit(2)
    try:
        target.write_text(strip_ids(text), encoding="utf-8")
    except OSError as exc:
        typer.echo(f"error: cannot write {target}: {exc.strerror or exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(f"{_summary(report)}\nexport: wrote {target}")


def _pdf_dict(report: PdfReport) -> dict[str, object]:
    return {
        "ok": report.ok,
        "pages": report.pages,
        "images": report.images,
        "source_words": report.source_words,
        "thresholds": {
            "token_recall": MIN_TOKEN_RECALL,
            "header_recall": MIN_HEADER_RECALL,
            "pair_recall": MIN_PAIR_RECALL,
        },
        "recalls": [
            {
                "order": r.order,
                "words": r.words,
                "token_recall": r.token,
                "header_recall": r.header,
                "pair_recall": r.pair,
            }
            for r in report.recalls
        ],
        "findings": [_as_dict(f) for f in report.findings],
    }


@app.command("pdf-check")
def pdf_check_command(pdf: Path, source: SourceOption, json_output: JsonOption = False) -> None:
    """Check that a resume PDF gives its text back, in order, the way an ATS reads it."""
    try:
        report = check_pdf(read_text(source), read_pdf(pdf))
    except EvidenceError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps(_pdf_dict(report)))
    else:
        for finding in report.findings:
            _show(str(pdf), finding)
        for r in report.recalls:
            typer.echo(
                f"  {r.order}: {r.words} words read, token recall {r.token:.1%}, "
                f"header recall {r.header:.1%}, pair recall {r.pair:.1%}"
            )
        verdict = "ok" if report.ok else f"FAIL ({len(report.findings)})"
        typer.echo(
            f"pdf-check: {verdict}. {report.pages} page(s), {report.images} image(s), "
            f"{report.source_words} words in the source. Needs token recall "
            f"{MIN_TOKEN_RECALL:.0%}, header recall {MIN_HEADER_RECALL:.0%} and pair recall "
            f"{MIN_PAIR_RECALL:.0%}"
        )
    raise typer.Exit(0 if report.ok else 1)
