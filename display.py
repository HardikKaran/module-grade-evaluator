def print_results(
    modules: list[dict],
    current: float,
    target: float,
    required: float | None,
    predictions: dict[str, float] | None = None,
    required_after: float | None = None,
) -> None:
    predictions = predictions or {}
    print("\n--- Results ---")
    for m in modules:
        pct = round(m["current_score"] * 100, 1)
        if m["is_complete"]:
            print(f"  {m['name']}: {pct}% (complete)")
        elif not m["tasks"]:
            if m["name"] in predictions:
                pred_pct = round(predictions[m["name"]] * 100, 1)
                print(f"  {m['name']}: no scores yet  |  predicted: {pred_pct}%")
            else:
                print(f"  {m['name']}: no scores yet (placeholder)")
        else:
            remaining_pct = round(m["remaining_fraction"] * 100, 1)
            if m["name"] in predictions:
                pred_pct = round(predictions[m["name"]] * 100, 1)
                print(f"  {m['name']}: {pct}% (incomplete, {remaining_pct}% remaining)  |  predicted: {pred_pct}%")
            else:
                print(f"  {m['name']}: {pct}% (incomplete — {remaining_pct}% of module remaining)")

    print(f"\nCurrent year grade: {round(current * 100, 1)}%")
    print(f"Target year grade:  {round(target * 100, 1)}%")

    if required is None:
        if current >= target:
            print("Already on track to hit the target — no remaining assessments needed.")
    elif required <= 1.0:
        print(f"Required score on all remaining assessments: {round(required * 100, 1)}%")
    else:
        print(
            f"Required score on all remaining assessments: {round(required * 100, 1)}%"
            f" (not achievable — target of {round(target * 100)}% is out of reach)"
        )

    if predictions:
        if required_after is None:
            if current >= target:
                print("With predictions applied: already on track.")
        elif required_after <= 1.0:
            print(f"Required score on unpredicted assessments (given predictions): {round(required_after * 100, 1)}%")
        else:
            print(
                f"Required score on unpredicted assessments (given predictions): {round(required_after * 100, 1)}%"
                f" (not achievable)"
            )


def print_prediction(predicted: float, target: float) -> None:
    gap = predicted - target
    print(f"\nPredicted year grade: {round(predicted * 100, 1)}%")
    if gap >= 0:
        print(f"  {round(gap * 100, 1)}% above target of {round(target * 100, 1)}%")
    else:
        print(f"  {round(abs(gap) * 100, 1)}% below target of {round(target * 100, 1)}%")
