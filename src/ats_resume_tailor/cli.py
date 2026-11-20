"""Command line interface. Thin: parse arguments, call core, print.

Exit codes: 0 clean, 1 a check failed, 2 the input could not be used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ats_resume_tailor import __version__
from ats_resume_tailor.adapters.files import load_evidence, read_text
from ats_resume_tailor.core.models import EvidenceError
from ats_resume_tailor.core.template import EVIDENCE_TEMPLATE
from ats_resume_tailor.core.verify import Finding, check_evidence, verify

app = typer.Typer(
    help="Check that every line of a resume traces to evidence you verified.",
    no_args_is_help=True,
)

EvidenceOption = Annotated[
    Path, typer.Option("--evidence", "-e", help="Path to your evidence.yaml.")
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
def verify_command(resume: Path, evidence: EvidenceOption, json_output: JsonOption = False) -> None:
    """Check an annotated resume against the evidence bank."""
    try:
        report = verify(read_text(resume), load_evidence(evidence))
    except EvidenceError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
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
        verdict = "ok" if report.ok else "FAIL"
        typer.echo(
            f"verify: {verdict}. {len(report.failures)} fail, {len(report.not_checked)} not "
            f"checked, {report.claim_lines} claim lines, {report.skill_items} skill lines, "
            f"{report.unchecked_headings} heading lines not checked"
        )
    raise typer.Exit(0 if report.ok else 1)
