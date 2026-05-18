import json
import os

GRADES_FILE = "grades.json"

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
DEFAULT_THEME = "LightGrey1"


def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
        return {"theme": str(data.get("theme", DEFAULT_THEME))}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"theme": DEFAULT_THEME}


def save_settings(settings: dict) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def _migrate_flat(data: dict) -> tuple[list[dict], int]:
    """Wrap old flat-format data (top-level 'modules') into a single-year list."""
    year = {
        "name": "Year 1",
        "weight": 1.0,
        "target": data.get("target_year_score", 0.70),
        "modules": data["modules"],
        "predictions": data.get("predictions", {}),
    }
    return [year], 0


def load_years(path: str = GRADES_FILE) -> tuple[list[dict], int]:
    with open(path) as f:
        data = json.load(f)
    if "modules" in data:
        return _migrate_flat(data)
    years = data["years"]
    active_idx = data.get("active_year_index", 0)
    return years, active_idx


def save_years(path: str, years: list[dict], active_idx: int) -> None:
    output = {
        "years": years,
        "active_year_index": active_idx,
    }
    with open(path, "w") as f:
        json.dump(output, f, indent=2)


# ---------------------------------------------------------------------------
# Legacy helpers kept for app.py compatibility
# ---------------------------------------------------------------------------

def load_grades(path: str = GRADES_FILE) -> tuple[list[dict], dict, float]:
    years, _ = load_years(path)
    y = years[0]
    return y["modules"], y.get("predictions", {}), y.get("target", 0.70)


def save_grades(
    path: str,
    modules: list[dict],
    predictions: dict,
    current: float,
    target: float,
    required: float | None,
) -> None:
    output = {
        "modules": modules,
        "predictions": predictions,
        "current_year_score": round(current, 6),
        "target_year_score": target,
        "required_score_on_remaining": round(required, 6) if required is not None else None,
    }
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
