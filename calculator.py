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


def compute_prediction(modules: list[dict], predictions: dict[str, list]) -> float:
    predicted = 0.0
    for m in modules:
        predicted += m["current_score"] * m["module_weight"]
        if not m["is_complete"] and m["name"] in predictions:
            for task in predictions[m["name"]]:
                predicted += task["score"] * task["weight"] * m["module_weight"]
    return predicted


def compute_required_after_predictions(
    modules: list[dict], predictions: dict[str, list], target: float
) -> float | None:
    predicted_year = compute_prediction(modules, predictions)
    remaining_unpredicted = 0.0
    for m in modules:
        if not m["is_complete"]:
            if m["name"] in predictions:
                pred_weight = sum(t["weight"] for t in predictions[m["name"]])
                leftover = max(0.0, m["remaining_fraction"] - pred_weight)
                remaining_unpredicted += leftover * m["module_weight"]
            else:
                remaining_unpredicted += m["remaining_fraction"] * m["module_weight"]
    if remaining_unpredicted <= 0:
        return None
    return (target - predicted_year) / remaining_unpredicted


def compute_avg_required_incomplete(modules: list[dict], target: float) -> float | None:
    """Average required grade for incomplete modules only."""
    current, _ = compute_current(modules)
    incomplete_remaining = sum(
        m["remaining_fraction"] * m["module_weight"]
        for m in modules
        if not m["is_complete"]
    )
    if incomplete_remaining <= 0:
        return None
    return (target - current) / incomplete_remaining
