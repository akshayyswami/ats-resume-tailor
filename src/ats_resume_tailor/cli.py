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
from ats_resume_tailor.core.export import strip_ids
from ats_resume_tailor.core.gaps import GapTable
from ats_resume_tailor.core.models import EvidenceError
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


def _as_dict(finding: Finding) -> dict[str, object]:
    return {
        "rule": finding.rule,
        "line": finding.line,
        "status": finding.status,
        "message": finding.message,
    }


def _show(label: str, finding: Finding) -> None:
    where = f"{label}:{finding.line}" if finding.line else label
    typer.echo(f"{where}: {finding.status.replace('_', ' ')} {finding.rule}: {finding.message}")


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
    if path.exists():
        typer.echo(f"{path} already exists; not overwriting it", err=True)
        raise typer.Exit(1)
    path.write_text(EVIDENCE_TEMPLATE, encoding="utf-8")
    typer.echo(f"wrote {path}. Replace the example fact, then run: check-evidence {path}")


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
    if target.resolve() == resume.resolve():
        typer.echo("error: the output would overwrite the annotated resume", err=True)
        raise typer.Exit(2)
    target.write_text(strip_ids(text), encoding="utf-8")
    typer.echo(f"{_summary(report)}\nexport: wrote {target}")
