def compute_current(modules: list[dict]) -> tuple[float, float]:
    current_year_score = sum(m["current_score"] * m["module_weight"] for m in modules)
    remaining_year_weight = sum(
        m["remaining_fraction"] * m["module_weight"] for m in modules if not m["is_complete"]
    )
    return current_year_score, remaining_year_weight


def compute_required(current: float, remaining_weight: float, target: float) -> float | None:
    if remaining_weight <= 0:
        return None
    return (target - current) / remaining_weight


def compute_prediction(modules: list[dict], predictions: dict[str, float]) -> float:
    predicted = 0.0
    for m in modules:
        predicted += m["current_score"] * m["module_weight"]
        if not m["is_complete"] and m["name"] in predictions:
            predicted += predictions[m["name"]] * m["remaining_fraction"] * m["module_weight"]
    return predicted


def compute_required_after_predictions(
    modules: list[dict], predictions: dict[str, float], target: float
) -> float | None:
    predicted_year = compute_prediction(modules, predictions)
    remaining_unpredicted = sum(
        m["remaining_fraction"] * m["module_weight"]
        for m in modules
        if not m["is_complete"] and m["name"] not in predictions
    )
    if remaining_unpredicted <= 0:
        return None
    return (target - predicted_year) / remaining_unpredicted
