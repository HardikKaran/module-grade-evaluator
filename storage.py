import json

GRADES_FILE = "grades.json"


def load_grades(path: str = GRADES_FILE) -> list[dict]:
    with open(path) as f:
        return json.load(f)["modules"]


def save_grades(path: str, modules: list[dict], current: float, target: float, required: float | None) -> None:
    output = {
        "modules": modules,
        "current_year_score": round(current, 6),
        "target_year_score": target,
        "required_score_on_remaining": round(required, 6) if required is not None else None,
    }
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
