CLASSIFICATIONS = [("1st", 0.70), ("2:1", 0.60), ("2:2", 0.50), ("3rd", 0.40)]


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
    current, _ = compute_current(modules)
    incomplete_remaining = sum(
        m["remaining_fraction"] * m["module_weight"]
        for m in modules
        if not m["is_complete"]
    )
    if incomplete_remaining <= 0:
        return None
    return (target - current) / incomplete_remaining


def compute_degree_overall(years: list[dict]) -> float:
    """Weighted sum of each year's current score by its year weight."""
    return sum(
        (y.get("current_year_score") or compute_current(y["modules"])[0]) * y["weight"]
        for y in years
    )


def compute_degree_classification(overall_score: float) -> str:
    for label, boundary in CLASSIFICATIONS:
        if overall_score >= boundary:
            return label
    return "Below 3rd"


def compute_classification_gaps(
    current: float, remaining_weight: float
) -> dict[str, float | None]:
    """Required score on remaining weight to reach each UK degree classification boundary.

    Returns None for a class if it is already achieved or if there is no remaining weight.
    """
    gaps = {}
    for label, boundary in CLASSIFICATIONS:
        if current >= boundary:
            gaps[label] = None  # already achieved
        elif remaining_weight <= 0:
            gaps[label] = float("inf")  # no remaining weight, can't reach it
        else:
            gaps[label] = (boundary - current) / remaining_weight
    return gaps
