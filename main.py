import json
import os

TARGET = 0.70
modules = []

if os.path.exists("grades.json"):
    if input("grades.json found. Load existing data? Y/N: ")[:1].upper() == 'Y':
        with open("grades.json") as f:
            modules = json.load(f)["modules"]
        print(f"Loaded {len(modules)} module(s).")

while True:
    print("\nWhat would you like to do?")
    print("  1. Add a new module (with scores)")
    print("  2. Update an incomplete module")
    print("  3. Add a placeholder module (no scores yet)")
    print("  4. Show results and save")
    choice = input("Choice: ").strip()

    if choice == '1':
        name = input("Module name: ")
        task_scores = []
        task_weights = []
        module_score = 0.0
        i = 0
        inner = True
        while inner:
            task_scores.append(float(input("Input Task Score (decimal): ")))
            task_weights.append(float(input("Input Task Weight (decimal): ")))
            module_score += task_scores[i] * task_weights[i]
            i += 1
            inner = input("Add more tasks? Y/N: ")[:1].upper() == 'Y'
        is_complete = input("Is '" + name + "' fully complete? Y/N: ")[:1].upper() == 'Y'
        remaining_fraction = 0.0 if is_complete else round(1.0 - sum(task_weights), 10)
        module_weight = float(input("Input weight of '" + name + "' toward year (decimal): "))
        modules.append({
            "name": name,
            "tasks": [{"score": s, "weight": w} for s, w in zip(task_scores, task_weights)],
            "current_score": module_score,
            "module_weight": module_weight,
            "is_complete": is_complete,
            "remaining_fraction": remaining_fraction,
        })

    elif choice == '2':
        incomplete = [m for m in modules if not m["is_complete"]]
        if not incomplete:
            print("No incomplete modules.")
            continue
        print("Incomplete modules:")
        for i, m in enumerate(incomplete):
            label = "no scores yet" if not m["tasks"] else f"{round(m['remaining_fraction'] * 100)}% remaining"
            print(f"  {i + 1}. {m['name']} ({label})")
        idx = int(input("Select module number: ")) - 1
        if idx < 0 or idx >= len(incomplete):
            print("Invalid selection.")
            continue
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

    elif choice == '3':
        name = input("Module name: ")
        module_weight = float(input("Input weight of '" + name + "' toward year (decimal): "))
        modules.append({
            "name": name,
            "tasks": [],
            "current_score": 0.0,
            "module_weight": module_weight,
            "is_complete": False,
            "remaining_fraction": 1.0,
        })
        print(f"Added '{name}' as a placeholder.")

    elif choice == '4':
        current_year_score = sum(m["current_score"] * m["module_weight"] for m in modules)
        remaining_year_weight = sum(
            m["remaining_fraction"] * m["module_weight"] for m in modules if not m["is_complete"]
        )

        print("\n--- Results ---")
        for m in modules:
            pct = round(m["current_score"] * 100, 1)
            if m["is_complete"]:
                print(f"{m['name']}: {pct}% (complete)")
            elif not m["tasks"]:
                print(f"{m['name']}: no scores yet (placeholder)")
            else:
                print(f"{m['name']}: {pct}% (incomplete — {round(m['remaining_fraction'] * 100, 1)}% of module remaining)")

        print(f"Current year grade: {round(current_year_score * 100, 1)}%")
        print(f"Target year grade: {round(TARGET * 100, 1)}%")

        required_score = None
        if remaining_year_weight > 0:
            required_score = (TARGET - current_year_score) / remaining_year_weight
            if required_score <= 1.0:
                print(f"Required score on remaining assessments: {round(required_score * 100, 1)}%")
            else:
                print(f"Required score on remaining assessments: {round(required_score * 100, 1)}% (not achievable — target of {round(TARGET * 100)}% is out of reach)")
        elif current_year_score >= TARGET:
            print("Already on track to hit the target — no remaining assessments needed.")

        output = {
            "modules": modules,
            "current_year_score": round(current_year_score, 6),
            "target_year_score": TARGET,
            "required_score_on_remaining": round(required_score, 6) if required_score is not None else None,
        }
        with open("grades.json", "w") as f:
            json.dump(output, f, indent=2)
        print("\nResults saved to grades.json")
        break
