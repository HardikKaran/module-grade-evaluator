import os
from calculator import compute_current, compute_prediction, compute_required, compute_required_after_predictions
from display import print_results, print_prediction
from storage import GRADES_FILE, load_grades, save_grades

TARGET = 0.70


def input_new_module() -> dict:
    name = input("Module name: ")
    task_scores, task_weights = [], []
    module_score = 0.0
    i = 0
    inner = True
    while inner:
        task_scores.append(float(input("Input Task Score (decimal): ")))
        task_weights.append(float(input("Input Task Weight (decimal): ")))
        module_score += task_scores[i] * task_weights[i]
        i += 1
        inner = input("Add more tasks? Y/N: ")[:1].upper() == 'Y'
    is_complete = input(f"Is '{name}' fully complete? Y/N: ")[:1].upper() == 'Y'
    remaining_fraction = 0.0 if is_complete else round(1.0 - sum(task_weights), 10)
    module_weight = float(input(f"Input weight of '{name}' toward year (decimal): "))
    return {
        "name": name,
        "tasks": [{"score": s, "weight": w} for s, w in zip(task_scores, task_weights)],
        "current_score": module_score,
        "module_weight": module_weight,
        "is_complete": is_complete,
        "remaining_fraction": remaining_fraction,
    }


def input_update_module(modules: list[dict]) -> None:
    incomplete = [m for m in modules if not m["is_complete"]]
    if not incomplete:
        print("No incomplete modules.")
        return
    print("Incomplete modules:")
    for i, m in enumerate(incomplete):
        label = "no scores yet" if not m["tasks"] else f"{round(m['remaining_fraction'] * 100)}% remaining"
        print(f"  {i + 1}. {m['name']} ({label})")
    try:
        idx = int(input("Select module number: ")) - 1
    except ValueError:
        print("Invalid input.")
        return
    if idx < 0 or idx >= len(incomplete):
        print("Invalid selection.")
        return
    m = incomplete[idx]
    inner = True
    while inner:
        score = float(input("Input Task Score (decimal): "))
        weight = float(input("Input Task Weight (decimal): "))
        m["tasks"].append({"score": score, "weight": weight})
        m["current_score"] += score * weight
        inner = input("Add more tasks? Y/N: ")[:1].upper() == 'Y'
    m["is_complete"] = input(f"Is '{m['name']}' now fully complete? Y/N: ")[:1].upper() == 'Y'
    entered_weight = sum(t["weight"] for t in m["tasks"])
    m["remaining_fraction"] = 0.0 if m["is_complete"] else round(1.0 - entered_weight, 10)


def input_placeholder_module() -> dict:
    name = input("Module name: ")
    module_weight = float(input(f"Input weight of '{name}' toward year (decimal): "))
    print(f"Added '{name}' as a placeholder.")
    return {
        "name": name,
        "tasks": [],
        "current_score": 0.0,
        "module_weight": module_weight,
        "is_complete": False,
        "remaining_fraction": 1.0,
    }


def input_prediction(modules: list[dict], predictions: dict[str, float]) -> None:
    incomplete = [m for m in modules if not m["is_complete"]]
    if not incomplete:
        print("No incomplete modules to predict.")
        return
    print("\n--- Grade Prediction ---")
    for m in incomplete:
        label = "placeholder, 100% of module" if not m["tasks"] else f"{round(m['remaining_fraction'] * 100)}% of module"
        add = input(f"  Add prediction for '{m['name']}' ({label} remaining)? Y/N: ")
        if add[:1].upper() == 'Y':
            predictions[m["name"]] = float(input(f"    Predicted score (decimal): "))
    predicted = compute_prediction(modules, predictions)
    print_prediction(predicted, TARGET)


def input_convert_prediction(modules: list[dict], predictions: dict[str, float]) -> None:
    predicted_modules = [m for m in modules if not m["is_complete"] and m["name"] in predictions]
    if not predicted_modules:
        print("No predicted modules to convert.")
        return
    print("Modules with predictions:")
    for i, m in enumerate(predicted_modules):
        pred_pct = round(predictions[m["name"]] * 100, 1)
        print(f"  {i + 1}. {m['name']} (predicted: {pred_pct}%)")
    try:
        idx = int(input("Select module number: ")) - 1
    except ValueError:
        print("Invalid input.")
        return
    if idx < 0 or idx >= len(predicted_modules):
        print("Invalid selection.")
        return
    m = predicted_modules[idx]
    obtained = float(input(f"Obtained score for the remaining {round(m['remaining_fraction'] * 100)}% of '{m['name']}' (decimal): "))
    m["tasks"].append({"score": obtained, "weight": m["remaining_fraction"]})
    m["current_score"] += obtained * m["remaining_fraction"]
    m["is_complete"] = input(f"Is '{m['name']}' now fully complete? Y/N: ")[:1].upper() == 'Y'
    entered_weight = sum(t["weight"] for t in m["tasks"])
    m["remaining_fraction"] = 0.0 if m["is_complete"] else round(1.0 - entered_weight, 10)
    del predictions[m["name"]]
    print(f"Updated '{m['name']}' with obtained score and removed prediction.")


def run() -> None:
    modules: list[dict] = []
    predictions: dict[str, float] = {}

    if os.path.exists(GRADES_FILE):
        if input(f"{GRADES_FILE} found. Load existing data? Y/N: ")[:1].upper() == 'Y':
            modules, predictions = load_grades(GRADES_FILE)
            print(f"Loaded {len(modules)} module(s), {len(predictions)} prediction(s).")

    while True:
        print("\nWhat would you like to do?")
        print("  1. Add a new module (with scores)")
        print("  2. Update an incomplete module")
        print("  3. Add a placeholder module (no scores yet)")
        print("  4. Show results and save")
        print("  5. Run grade prediction")
        print("  6. Convert predicted score to obtained")
        choice = input("Choice: ").strip()

        if choice == '1':
            modules.append(input_new_module())
        elif choice == '2':
            input_update_module(modules)
        elif choice == '3':
            modules.append(input_placeholder_module())
        elif choice == '4':
            current, remaining_weight = compute_current(modules)
            required = compute_required(current, remaining_weight, TARGET)
            required_after = compute_required_after_predictions(modules, predictions, TARGET) if predictions else None
            print_results(modules, current, TARGET, required, predictions, required_after)
            save_grades(GRADES_FILE, modules, predictions, current, TARGET, required)
            print(f"\nResults saved to {GRADES_FILE}")
            break
        elif choice == '5':
            input_prediction(modules, predictions)
        elif choice == '6':
            input_convert_prediction(modules, predictions)
        else:
            print("Please enter 1–6.")
