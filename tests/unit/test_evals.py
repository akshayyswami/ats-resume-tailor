"""The eval is part of the test suite: every planted fault caught, every clean input allowed."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load_measure() -> ModuleType:
    # `python evals/measure.py` has evals/ on the path; a test run has to add it.
    if str(ROOT / "evals") not in sys.path:
        sys.path.insert(0, str(ROOT / "evals"))
    spec = importlib.util.spec_from_file_location("measure", ROOT / "evals" / "measure.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure"] = module
    spec.loader.exec_module(module)
    return module


def test_the_fault_matrix_is_perfect() -> None:
    counts, problems = _load_measure().fault_matrix()
    assert problems == []
    assert counts["must_catch_caught"] == counts["must_catch_total"] == 40
    assert counts["must_allow_passed"] == counts["must_allow_total"] == 12
    assert counts["rules_covered"] == counts["rules_total"] == 26


def test_measure_exits_zero_and_floors_are_checked() -> None:
    measure = _load_measure()
    assert measure.main() == 0
    assert measure.violations({}) == []
    measure.FLOORS["x"] = 1.0
    try:
        assert measure.violations({"x": 0.5}) == ["x=0.5 is below its floor 1.0"]
        assert measure.violations({}) == ["x=None is below its floor 1.0"]
    finally:
        del measure.FLOORS["x"]
