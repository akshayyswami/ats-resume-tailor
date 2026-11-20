"""Print ONE JSON object holding every number the README quotes.

Offline and deterministic: the planted faults in faults.yaml are run through the real checks.
No network, no timestamps, no live model. `make evals` redirects the output to results/latest.json.

Fail closed: exit non-zero if a planted fault is missed, a clean input is wrongly flagged, or a
rule in core/verify.py or core/pdfcheck.py has no planted fault. It never prints a good-looking
number to cover a failure.

The fabrication measurement reads raw model outputs saved under evals/baseline/, so it is
recomputed here without a model. The PDF figures come from the fixture PDFs in fixtures/pdfs/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml
from fabrication import detector_cases, load_jds, score

from ats_resume_tailor.adapters.files import load_evidence, load_gaps, read_text
from ats_resume_tailor.adapters.pdf import read_pdf
from ats_resume_tailor.core.models import EvidenceError
from ats_resume_tailor.core.pdfcheck import (
    MIN_HEADER_RECALL,
    MIN_PAIR_RECALL,
    MIN_TOKEN_RECALL,
    PDF_RULES,
    PdfReport,
    check_pdf,
)
from ats_resume_tailor.core.verify import ALL_RULES, Finding, check_evidence, verify

EVALS = Path(__file__).resolve().parent
PERSONA_BANK = EVALS.parent / "examples" / "persona" / "evidence.yaml"

# Floors for the headline numbers. A real drop trips CI; ordinary noise does not.
# The fault matrix has no floor: it must be perfect.
FLOORS: dict[str, float] = {}


def _run(entry: dict[str, Any]) -> list[Finding]:
    """The FAIL findings the real checks produce for one entry."""
    target = EVALS / entry["input"]
    if entry["kind"] == "bank":
        return check_evidence(load_evidence(target))
    if entry["kind"] == "pdf":
        return list(_pdf_report(entry).findings)
    bank = EVALS / entry["bank"] if "bank" in entry else PERSONA_BANK
    gaps = load_gaps(EVALS / entry["gaps"]) if "gaps" in entry else None
    return verify(read_text(target), load_evidence(bank), gaps).failures


def _pdf_report(entry: dict[str, Any]) -> PdfReport:
    return check_pdf(read_text(EVALS / entry["source"]), read_pdf(EVALS / entry["input"]))


def pdf_figures() -> dict[str, Any]:
    """The measured recalls for every PDF fixture, and the thresholds they are judged by."""
    spec = yaml.safe_load((EVALS / "faults.yaml").read_text(encoding="utf-8"))
    fixtures: dict[str, Any] = {}
    for entry in [*spec["must_catch"], *spec["must_allow"]]:
        if entry["kind"] != "pdf":
            continue
        report = _pdf_report(entry)
        by_order = {
            ("stream" if r.order.startswith("stream") else "visual"): {
                "words": r.words,
                "token": r.token,
                "header": r.header,
                "pair": r.pair,
            }
            for r in report.recalls
        }
        fixtures[Path(entry["input"]).stem] = {
            "images": report.images,
            "pages": report.pages,
            "source_words": report.source_words,
            **by_order,
        }
    return {
        "thresholds": {
            "token": MIN_TOKEN_RECALL,
            "header": MIN_HEADER_RECALL,
            "pair": MIN_PAIR_RECALL,
        },
        "fixtures": fixtures,
    }


def fault_matrix() -> tuple[dict[str, Any], list[str]]:
    """Run every planted fault and clean input. Returns the counts and any problems."""
    spec = yaml.safe_load((EVALS / "faults.yaml").read_text(encoding="utf-8"))
    problems: list[str] = []
    caught = 0
    covered: set[str] = set()
    for entry in spec["must_catch"]:
        covered.add(entry["expect_rule"])
        try:
            rules = {f.rule for f in _run(entry)}
        except EvidenceError as exc:
            problems.append(f"must_catch {entry['id']}: could not run: {exc}")
            continue
        if entry["expect_rule"] in rules:
            caught += 1
        else:
            problems.append(
                f"must_catch {entry['id']}: expected {entry['expect_rule']}, "
                f"got {sorted(rules) or 'nothing'}"
            )
    passed = 0
    for entry in spec["must_allow"]:
        try:
            failures = _run(entry)
        except EvidenceError as exc:
            problems.append(f"must_allow {entry['id']}: could not run: {exc}")
            continue
        if failures:
            flagged = sorted({f.rule for f in failures})
            problems.append(f"must_allow {entry['id']}: wrongly flagged {flagged}")
        else:
            passed += 1
    every_rule = (*ALL_RULES, *PDF_RULES)
    untested = sorted(set(every_rule) - covered)
    for rule in untested:
        problems.append(f"rule {rule} has no planted fault in faults.yaml")
    counts = {
        "must_catch_total": len(spec["must_catch"]),
        "must_catch_caught": caught,
        "must_allow_total": len(spec["must_allow"]),
        "must_allow_passed": passed,
        "rules_total": len(every_rule),
        "rules_covered": len(covered & set(every_rule)),
    }
    return counts, problems


def measure() -> tuple[dict[str, object], list[str]]:
    """Return every figure the README quotes, and any problems that must fail the run."""
    faults, problems = fault_matrix()
    persona = load_evidence(PERSONA_BANK)
    jds = load_jds(EVALS)
    detector, detector_problems = detector_cases(EVALS, jds)
    fabrication, fabrication_problems = score(EVALS, jds, persona)
    results: dict[str, object] = {
        "faults": faults,
        "persona": {"facts": len(persona.facts)},
        "detector": detector,
        "fabrication": fabrication,
        "pdf": pdf_figures(),
    }
    return results, problems + detector_problems + fabrication_problems


def violations(results: dict[str, object]) -> list[str]:
    """Return a message for every floor that is not met."""
    problems: list[str] = []
    for key, floor in FLOORS.items():
        value = results.get(key)
        if not isinstance(value, (int, float)) or value < floor:
            problems.append(f"{key}={value!r} is below its floor {floor}")
    return problems


def main() -> int:
    results, problems = measure()
    problems += violations(results)
    for problem in problems:
        print(f"evals: {problem}", file=sys.stderr)
    print(json.dumps(results, indent=2, sort_keys=True))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
