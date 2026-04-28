"""Pure data model and scoring helpers — no Qt or matplotlib here."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

CLASS_BOUNDARIES: list[tuple[float, str]] = [
    (70.0, "1st"),
    (60.0, "2:1"),
    (50.0, "2:2"),
    (40.0, "3rd"),
]


@dataclass
class Task:
    name: str = "Task"
    weight: float = 0.0
    score: Optional[float] = None


@dataclass
class Module:
    name: str = "Module"
    credits: float = 0.0
    target: Optional[float] = None
    tasks: list[Task] = field(default_factory=list)


@dataclass
class Year:
    name: str = "Year"
    target: Optional[float] = None
    modules: list[Module] = field(default_factory=list)


def completed_weight(module: Module) -> float:
    return sum(t.weight for t in module.tasks if t.score is not None)


def total_weight(module: Module) -> float:
    return sum(t.weight for t in module.tasks)


def module_score(module: Module) -> Optional[float]:
    """Provisional weighted average over completed tasks (0..100), or None if nothing entered."""
    cw = completed_weight(module)
    if cw <= 0:
        return None
    s = sum(t.score * t.weight for t in module.tasks if t.score is not None)
    return s / cw


def projected_module_score(module: Module, fill: float = 0.0) -> Optional[float]:
    """Score assuming every uncompleted task scores `fill` percent.

    If total weight is 0, returns None.
    """
    tw = total_weight(module)
    if tw <= 0:
        return None
    s = 0.0
    for t in module.tasks:
        score = t.score if t.score is not None else fill
        s += score * t.weight
    return s / tw


def year_score(year: Year, fill_unentered: Optional[float] = None) -> Optional[float]:
    """Credit-weighted average across modules.

    By default modules with no entered tasks are skipped. If `fill_unentered` is
    given, uncompleted tasks are assumed to score that value.
    """
    total_credits = 0.0
    weighted = 0.0
    for m in year.modules:
        if m.credits <= 0:
            continue
        if fill_unentered is None:
            ms = module_score(m)
        else:
            ms = projected_module_score(m, fill=fill_unentered)
        if ms is None:
            continue
        weighted += ms * m.credits
        total_credits += m.credits
    if total_credits <= 0:
        return None
    return weighted / total_credits


def class_of(pct: Optional[float]) -> str:
    if pct is None:
        return "—"
    for threshold, label in CLASS_BOUNDARIES:
        if pct >= threshold:
            return label
    return "Fail"


def module_status(module: Module) -> str:
    """Short human-readable status used in the table."""
    tw = total_weight(module)
    cw = completed_weight(module)
    if tw == 0:
        return "no tasks"
    if abs(tw - 1.0) > 1e-6:
        return f"weights sum to {tw:.2f}"
    if cw == 0:
        return "not started"
    if cw < tw - 1e-6:
        return f"{cw * 100:.0f}% done"
    return "complete"
