import os
from calculator import compute_current, compute_required, compute_prediction
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


def input_prediction(modules: list[dict]) -> None:
    incomplete = [m for m in modules if not m["is_complete"]]
    if not incomplete:
        print("No incomplete modules to predict.")
        return
    print("\n--- Grade Prediction ---")
    predictions = {}
    for m in incomplete:
        label = "placeholder, 100% of module" if not m["tasks"] else f"{round(m['remaining_fraction'] * 100)}% of module"
        add = input(f"  Add prediction for '{m['name']}' ({label} remaining)? Y/N: ")
        if add[:1].upper() == 'Y':
            predictions[m["name"]] = float(input(f"    Predicted score (decimal): "))
    predicted = compute_prediction(modules, predictions)
    print_prediction(predicted, TARGET)


def run() -> None:
    modules: list[dict] = []

    if os.path.exists(GRADES_FILE):
        if input(f"{GRADES_FILE} found. Load existing data? Y/N: ")[:1].upper() == 'Y':
            modules = load_grades(GRADES_FILE)
            print(f"Loaded {len(modules)} module(s).")

    while True:
        print("\nWhat would you like to do?")
        print("  1. Add a new module (with scores)")
        print("  2. Update an incomplete module")
        print("  3. Add a placeholder module (no scores yet)")
        print("  4. Show results and save")
        print("  5. Run grade prediction")
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
            print_results(modules, current, TARGET, required)
            save_grades(GRADES_FILE, modules, current, TARGET, required)
            print(f"\nResults saved to {GRADES_FILE}")
            break
        elif choice == '5':
            input_prediction(modules)
        else:
            print("Please enter 1–5.")
