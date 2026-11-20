"""Print ONE JSON object holding every number the README quotes.

Offline and deterministic: the planted faults in faults.yaml are run through the real checks.
No network, no timestamps, no live model. `make evals` redirects the output to results/latest.json.

Fail closed: exit non-zero if a planted fault is missed, a clean input is wrongly flagged, or a rule
in core/verify.py has no planted fault. It never prints a good-looking number to cover a failure.

The fabrication measurement (M2) will read raw model outputs saved under evals/baseline/, so it
is recomputed here without a model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from ats_resume_tailor.adapters.files import load_evidence, read_text
from ats_resume_tailor.core.models import EvidenceError
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
    bank = EVALS / entry["bank"] if "bank" in entry else PERSONA_BANK
    return verify(read_text(target), load_evidence(bank)).failures


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
    untested = sorted(set(ALL_RULES) - covered)
    for rule in untested:
        problems.append(f"rule {rule} has no planted fault in faults.yaml")
    counts = {
        "must_catch_total": len(spec["must_catch"]),
        "must_catch_caught": caught,
        "must_allow_total": len(spec["must_allow"]),
        "must_allow_passed": passed,
        "rules_total": len(ALL_RULES),
        "rules_covered": len(covered & set(ALL_RULES)),
    }
    return counts, problems


def measure() -> tuple[dict[str, object], list[str]]:
    """Return every figure the README quotes, and any problems that must fail the run."""
    faults, problems = fault_matrix()
    persona = load_evidence(PERSONA_BANK)
    return {"faults": faults, "persona": {"facts": len(persona.facts)}}, problems


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
