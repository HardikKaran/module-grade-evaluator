"""JSON load/save for the Year data model."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.model import Module, Task, Year

SCHEMA_VERSION = 1


def save(year: Year, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": SCHEMA_VERSION, "year": asdict(year)}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load(path: Path) -> Year:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    data = raw["year"] if "year" in raw else raw  # tolerate flat files
    modules = [
        Module(
            name=m.get("name", "Module"),
            credits=float(m.get("credits", 0.0)),
            target=m.get("target"),
            tasks=[
                Task(
                    name=t.get("name", "Task"),
                    weight=float(t.get("weight", 0.0)),
                    score=t.get("score"),
                )
                for t in m.get("tasks", [])
            ],
        )
        for m in data.get("modules", [])
    ]
    return Year(
        name=data.get("name", "Year"),
        target=data.get("target"),
        modules=modules,
    )
