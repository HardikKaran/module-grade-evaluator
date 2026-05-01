import json

GRADES_FILE = "grades.json"


def load_grades(path: str = GRADES_FILE) -> tuple[list[dict], dict[str, float]]:
    with open(path) as f:
        data = json.load(f)
    return data["modules"], data.get("predictions", {})


def save_grades(
    path: str,
    modules: list[dict],
    predictions: dict[str, float],
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
