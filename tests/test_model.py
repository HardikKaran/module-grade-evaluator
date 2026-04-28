"""Smoke tests for scoring and required-score logic — no Qt involved."""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.calc.required import (
    required_for_module,
    required_for_year_uniform,
)
from src.model import (
    Module,
    Task,
    Year,
    class_of,
    module_score,
    projected_module_score,
    year_score,
)


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return math.isclose(a, b, abs_tol=tol)


def make_year() -> Year:
    return Year(
        name="Y2",
        target=70.0,
        modules=[
            Module(
                name="Maths",
                credits=15.0,
                target=70.0,
                tasks=[
                    Task(name="CW", weight=0.4, score=75.0),
                    Task(name="Exam", weight=0.6, score=None),
                ],
            ),
            Module(
                name="Physics",
                credits=15.0,
                target=65.0,
                tasks=[
                    Task(name="Lab", weight=0.3, score=80.0),
                    Task(name="Exam", weight=0.7, score=60.0),
                ],
            ),
        ],
    )


def test_module_score_partial():
    y = make_year()
    maths = y.modules[0]
    # Only the 0.4 weight CW is entered, with score 75 → 75 over completed weight
    assert approx(module_score(maths), 75.0)


def test_module_score_full():
    y = make_year()
    physics = y.modules[1]
    # 0.3*80 + 0.7*60 = 24 + 42 = 66
    assert approx(module_score(physics), 66.0)


def test_projected_module_score_zero_fill():
    y = make_year()
    maths = y.modules[0]
    # 0.4*75 + 0.6*0 = 30 → 30/1.0 = 30
    assert approx(projected_module_score(maths, 0.0), 30.0)


def test_year_score_credit_weighted():
    y = make_year()
    # Maths uses provisional 75, Physics 66; equal credits → 70.5
    assert approx(year_score(y), 70.5)


def test_required_for_module():
    y = make_year()
    maths = y.modules[0]
    # To hit 70 overall: 0.4*75 + 0.6*x = 70 → x = (70 - 30)/0.6 = 66.667
    req = required_for_module(maths, 70.0)
    assert req is not None
    assert approx(req.value, (70.0 - 30.0) / 0.6, tol=1e-4)
    assert req.feasible
    assert req.has_remaining


def test_required_for_year_uniform_feasible():
    y = make_year()
    # Maths exam (0.6 weight, 15 cr) is the only remaining task
    # contributed = 15*0.4*75 + 15*0.3*80 + 15*0.7*60 = 450 + 360 + 630 = 1440
    # total_units = 15*1.0 + 15*1.0 = 30
    # remaining = 30 - (15*0.4 + 15*0.3 + 15*0.7) = 30 - 21 = 9
    # need: (70*30 - 1440) / 9 = (2100 - 1440) / 9 = 660 / 9 ≈ 73.33
    req = required_for_year_uniform(y, 70.0)
    assert req is not None
    assert approx(req.value, 660.0 / 9.0, tol=1e-4)
    assert req.feasible


def test_required_for_year_infeasible():
    y = make_year()
    # Demand 99 — should flag infeasible (need >100 on remaining)
    req = required_for_year_uniform(y, 99.0)
    assert req is not None
    assert not req.feasible


def test_class_boundaries():
    assert class_of(72) == "1st"
    assert class_of(60) == "2:1"
    assert class_of(55) == "2:2"
    assert class_of(45) == "3rd"
    assert class_of(30) == "Fail"
    assert class_of(None) == "—"


def main() -> None:
    fns = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"ok  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
