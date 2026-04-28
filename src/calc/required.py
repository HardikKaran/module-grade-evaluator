"""'What do I need to score?' calculations — closed form, no Qt."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.model import Module, Year, completed_weight, total_weight


@dataclass
class Required:
    """Required score on the *remaining* portion to hit a target.

    `value` is in percent (0..100). It can be negative (already exceeded the
    target) or above 100 (impossible). `feasible` is False when > 100,
    `trivial` is True when <= 0.
    """
    value: float
    feasible: bool
    trivial: bool
    has_remaining: bool

    @property
    def status(self) -> str:
        if not self.has_remaining:
            return "done"
        if self.trivial:
            return "achieved"
        if not self.feasible:
            return "impossible"
        if self.value <= 80:
            return "ok"
        if self.value <= 95:
            return "tight"
        return "very tight"


def required_for_module(module: Module, target: float) -> Optional[Required]:
    """Minimum average score needed on the remaining (uncompleted-weight) portion.

    Returns None if the module has no weight at all.
    """
    tw = total_weight(module)
    if tw <= 0:
        return None
    cw = completed_weight(module)
    contributed = sum(t.score * t.weight for t in module.tasks if t.score is not None)
    remaining = tw - cw
    if remaining <= 1e-9:
        # Everything entered already
        achieved = contributed / tw
        return Required(
            value=0.0,
            feasible=achieved >= target - 1e-9,
            trivial=True,
            has_remaining=False,
        )
    needed = (target * tw - contributed) / remaining
    return Required(
        value=needed,
        feasible=needed <= 100.0 + 1e-9,
        trivial=needed <= 0.0,
        has_remaining=True,
    )


def required_for_year_uniform(year: Year, target: float) -> Optional[Required]:
    """Single number: the score you'd need on every remaining task (across all
    modules) if you scored equally everywhere, to hit the year target.

    Uses credit-weight × task-weight as the contribution unit.
    """
    total_units = 0.0       # Σ credits_m * weight_t for all tasks with credits>0
    completed_units = 0.0
    contributed = 0.0
    for m in year.modules:
        if m.credits <= 0:
            continue
        for t in m.tasks:
            unit = m.credits * t.weight
            total_units += unit
            if t.score is not None:
                completed_units += unit
                contributed += t.score * unit
    if total_units <= 0:
        return None
    remaining = total_units - completed_units
    if remaining <= 1e-9:
        achieved = contributed / total_units
        return Required(
            value=0.0,
            feasible=achieved >= target - 1e-9,
            trivial=True,
            has_remaining=False,
        )
    needed = (target * total_units - contributed) / remaining
    return Required(
        value=needed,
        feasible=needed <= 100.0 + 1e-9,
        trivial=needed <= 0.0,
        has_remaining=True,
    )


def required_per_module_for_year(year: Year, target: float) -> dict[str, Optional[Required]]:
    """For each module, the average score required on its *remaining* portion
    so that — assuming all other modules score uniformly the same value —
    the year average hits the target.

    For simplicity we use the uniform-fill score for every module (including
    this one), giving each module the same required uplift on its remaining
    weight. This is the straightforward and intuitive interpretation: the
    'what do I need on the remaining work?' answer broken down per module.
    """
    uniform = required_for_year_uniform(year, target)
    out: dict[str, Optional[Required]] = {}
    for m in year.modules:
        if total_weight(m) <= 0 or m.credits <= 0:
            out[m.name] = None
            continue
        if uniform is None:
            out[m.name] = None
            continue
        cw = completed_weight(m)
        if cw >= total_weight(m) - 1e-9:
            out[m.name] = Required(0.0, True, True, False)
            continue
        out[m.name] = Required(
            value=uniform.value,
            feasible=uniform.feasible,
            trivial=uniform.trivial,
            has_remaining=True,
        )
    return out
