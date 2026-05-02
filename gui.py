import os
import PySimpleGUI as sg
from calculator import (
    compute_current,
    compute_prediction,
    compute_required,
    compute_required_after_predictions,
)
from storage import GRADES_FILE, load_grades, save_grades

TARGET = 0.70
COLS = 3


def pct(decimal: float) -> str:
    """Convert decimal (0.0-1.0) to percentage string like '72.0%'."""
    return f"{decimal * 100:.1f}%"


def compute_stats(modules: list, predictions: dict) -> dict:
    """Compute all stats: current, required, predicted, required_after."""
    current, remaining_weight = compute_current(modules)
    required = compute_required(current, remaining_weight, TARGET)
    predicted = compute_prediction(modules, predictions) if predictions else None
    required_after = (
        compute_required_after_predictions(modules, predictions, TARGET)
        if predictions
        else None
    )
    return {
        "current": current,
        "remaining_weight": remaining_weight,
        "required": required,
        "predicted": predicted,
        "required_after": required_after,
    }


def _recompute_module(m: dict) -> dict:
    """Recalculate current_score and remaining_fraction from tasks list."""
    m["current_score"] = sum(t["score"] * t["weight"] for t in m["tasks"])
    entered = sum(t["weight"] for t in m["tasks"])
    m["remaining_fraction"] = 0.0 if m["is_complete"] else round(1.0 - entered, 10)
    return m


def build_stats_bar(stats: dict) -> sg.Frame:
    """Build the top stats bar frame."""
    elements = [
        sg.Text(f"Current: {pct(stats['current'])}", font=("Arial", 10, "bold")),
        sg.VerticalSeparator(),
        sg.Text(f"Target: {pct(TARGET)}", font=("Arial", 10)),
    ]

    if stats["predicted"] is not None:
        elements.append(sg.VerticalSeparator())
        elements.append(
            sg.Text(f"Predicted: {pct(stats['predicted'])}", font=("Arial", 10))
        )

    elements.append(sg.VerticalSeparator())
    if stats["required"] is not None:
        if stats["required"] > 1.0:
            elements.append(
                sg.Text(
                    f"Required: {pct(stats['required'])} (UNACHIEVABLE)",
                    font=("Arial", 10),
                    text_color="red",
                )
            )
        else:
            elements.append(
                sg.Text(f"Required: {pct(stats['required'])}", font=("Arial", 10))
            )
    else:
        if stats["current"] >= TARGET:
            elements.append(
                sg.Text("On track!", font=("Arial", 10), text_color="green")
            )
        else:
            elements.append(
                sg.Text(
                    "Below target, no remaining assessments",
                    font=("Arial", 10),
                    text_color="orange",
                )
            )

    if stats["required_after"] is not None:
        elements.append(sg.VerticalSeparator())
        if stats["required_after"] > 1.0:
            elements.append(
                sg.Text(
                    f"After predictions: {pct(stats['required_after'])} (UNACHIEVABLE)",
                    font=("Arial", 10),
                    text_color="red",
                )
            )
        else:
            elements.append(
                sg.Text(
                    f"After predictions: {pct(stats['required_after'])}",
                    font=("Arial", 10),
                )
            )

    return sg.Frame("Year Statistics", [[*elements]], font=("Arial", 10, "bold"))


def build_module_card(module: dict, predictions: dict, idx: int) -> sg.Frame:
    """Build one module card frame."""
    name = module["name"]
    badge_text = "DONE" if module["is_complete"] else "IN PROGRESS"
    badge_color = ("white", "green") if module["is_complete"] else ("white", "orange")

    rows = [
        [
            sg.Text(name, font=("Arial", 11, "bold")),
            sg.Text(badge_text, font=("Arial", 9), text_color=badge_color[0], background_color=badge_color[1], pad=(10, 0)),
        ],
        [sg.Text(f"Weight: {pct(module['module_weight'])}", font=("Arial", 9))],
    ]

    for i, task in enumerate(module["tasks"]):
        task_name = task.get("name", "").strip() or f"Task {i + 1}"
        rows.append(
            [
                sg.Text(
                    f"{task_name}: {pct(task['score'])} / {pct(task['weight'])} wt",
                    font=("Arial", 9),
                )
            ]
        )

    if name in predictions and not module["is_complete"]:
        rows.append(
            [sg.Text(f"Predicted: {pct(predictions[name])}", font=("Arial", 9))]
        )

    rows.append(
        [
            sg.Text(
                f"Current score: {pct(module['current_score'])}",
                font=("Arial", 9, "bold"),
            )
        ]
    )
    rows.append([sg.Button("Edit Module", key=f"EDIT_{idx}", size=(12, 1))])

    return sg.Frame(
        "", rows, border_width=1, font=("Arial", 9), vertical_alignment="top"
    )


def build_module_grid(modules: list, predictions: dict) -> sg.Column:
    """Build scrollable module grid, completed first."""
    sorted_mods = (
        [(i, m) for i, m in enumerate(modules) if m["is_complete"]]
        + [(i, m) for i, m in enumerate(modules) if not m["is_complete"]]
    )

    cards = [build_module_card(m, predictions, i) for i, m in sorted_mods]

    if not cards:
        return None

    rows = [cards[j : j + COLS] for j in range(0, len(cards), COLS)]
    layout = [
        [
            sg.Column(
                [[card for card in row]],
                element_justification="left",
                vertical_alignment="top",
            )
        ]
        for row in rows
    ]

    return sg.Column(
        layout,
        scrollable=True,
        vertical_scroll_only=True,
        size=(900, 500),
        element_justification="left",
    )


def build_main_layout(modules: list, predictions: dict) -> list:
    """Build full main window layout."""
    stats = compute_stats(modules, predictions)
    stats_bar = build_stats_bar(stats)

    layout = [
        [stats_bar],
        [sg.HorizontalSeparator()],
    ]

    if modules:
        layout.append([sg.Button("Add Module", key="ADD_MODULE", size=(15, 1))])
        grid = build_module_grid(modules, predictions)
        if grid:
            layout.append([grid])
    else:
        layout.append(
            [
                sg.Text(
                    "No modules yet. Click 'Add Module' to get started.",
                    font=("Arial", 11),
                ),
                sg.Button("Add Module", key="ADD_MODULE_EMPTY", size=(15, 1)),
            ]
        )

    return layout


def make_main_window(modules: list, predictions: dict) -> sg.Window:
    """Create and return the main window."""
    layout = build_main_layout(modules, predictions)
    return sg.Window(
        "Module Grade Evaluator",
        layout,
        resizable=True,
        finalize=True,
        size=(1000, 700),
    )


def validate_percent(val: str, field_name: str) -> float | None:
    """Validate and convert percentage string (0-100) to decimal (0-1)."""
    try:
        pct_val = float(val.strip())
        if pct_val < 0 or pct_val > 100:
            sg.popup_error(
                f"{field_name} must be between 0 and 100",
                title="Invalid Input",
            )
            return None
        return pct_val / 100.0
    except ValueError:
        sg.popup_error(f"{field_name} must be a number", title="Invalid Input")
        return None


def validate_module_name(
    name: str, modules: list, editing_idx: int | None
) -> bool:
    """Validate module name (non-empty, not duplicate)."""
    if not name.strip():
        sg.popup_error("Module name cannot be empty", title="Invalid Input")
        return False

    for i, m in enumerate(modules):
        if i != editing_idx and m["name"].lower() == name.strip().lower():
            sg.popup_error("Module name already exists", title="Invalid Input")
            return False

    return True


def validate_task_weights(tasks: list) -> bool:
    """Validate task weights sum to <= 100%."""
    total = sum(t["weight"] for t in tasks)
    if total > 1.0 + 1e-9:
        sg.popup_error(
            f"Task weights exceed 100% (total: {pct(total)})",
            title="Invalid Weights",
        )
        return False
    return True


def build_task_rows(tasks: list) -> list:
    """Build task input rows for edit dialog."""
    rows = [
        [
            sg.Text("Task Name (optional)", font=("Arial", 9), size=(15, 1)),
            sg.Text("Score %", font=("Arial", 9), size=(10, 1)),
            sg.Text("Weight %", font=("Arial", 9), size=(10, 1)),
            sg.Text("", font=("Arial", 9), size=(5, 1)),
        ]
    ]

    for i, task in enumerate(tasks):
        rows.append(
            [
                sg.Input(
                    task.get("name", ""),
                    key=f"TASK_NAME_{i}",
                    size=(15, 1),
                    font=("Arial", 9),
                ),
                sg.Input(
                    f"{task['score'] * 100:.1f}",
                    key=f"TASK_SCORE_{i}",
                    size=(10, 1),
                    font=("Arial", 9),
                ),
                sg.Input(
                    f"{task['weight'] * 100:.1f}",
                    key=f"TASK_WEIGHT_{i}",
                    size=(10, 1),
                    font=("Arial", 9),
                ),
                sg.Button(
                    "X", key=f"DEL_TASK_{i}", size=(4, 1), button_color=("white", "red")
                ),
            ]
        )

    return rows


def open_module_dialog(
    module: dict | None, predictions: dict, idx: int | None, modules: list
) -> tuple[dict | None, dict, str]:
    """Open edit/add module dialog. Returns (module, predictions, action)."""
    is_edit = module is not None
    module = module or {
        "name": "",
        "tasks": [],
        "current_score": 0.0,
        "module_weight": 0.0,
        "is_complete": False,
        "remaining_fraction": 1.0,
    }

    tasks = [t.copy() for t in module["tasks"]]
    old_name = module["name"]
    other_modules = [m for i, m in enumerate(modules) if i != idx]

    while True:
        is_complete = module["is_complete"]

        task_rows = build_task_rows(tasks)
        layout = [
            [
                sg.Frame(
                    "Module Details",
                    [
                        [
                            sg.Text("Name:", font=("Arial", 10)),
                            sg.Input(
                                module["name"],
                                key="MOD_NAME",
                                size=(30, 1),
                                font=("Arial", 10),
                            ),
                        ],
                        [
                            sg.Text("Weight toward year (%):", font=("Arial", 10)),
                            sg.Input(
                                f"{module['module_weight'] * 100:.1f}",
                                key="MOD_WEIGHT",
                                size=(10, 1),
                                font=("Arial", 10),
                            ),
                        ],
                        [
                            sg.Checkbox(
                                "Module is complete",
                                default=is_complete,
                                key="MOD_COMPLETE",
                                font=("Arial", 10),
                            )
                        ],
                    ],
                    font=("Arial", 10, "bold"),
                )
            ],
            [
                sg.Frame(
                    "Tasks",
                    [*task_rows, [sg.Button("Add Task", key="ADD_TASK", size=(12, 1))]],
                    font=("Arial", 10, "bold"),
                )
            ],
        ]

        if not is_complete:
            layout.append(
                [
                    sg.Frame(
                        "Prediction (for remaining assessment)",
                        [
                            [
                                sg.Text("Predicted score (%):", font=("Arial", 10)),
                                sg.Input(
                                    f"{predictions.get(old_name, 0.0) * 100:.1f}"
                                    if old_name in predictions
                                    else "",
                                    key="PRED_SCORE",
                                    size=(10, 1),
                                    font=("Arial", 10),
                                ),
                            ],
                            [
                                sg.Text(
                                    "Leave blank to remove prediction",
                                    font=("Arial", 9),
                                    text_color="gray",
                                )
                            ],
                        ],
                        font=("Arial", 10, "bold"),
                    )
                ]
            )

        buttons = [
            sg.Button("Save", key="SAVE", size=(10, 1)),
            sg.Button("Cancel", key="CANCEL", size=(10, 1)),
        ]
        if is_edit:
            buttons.insert(
                1,
                sg.Button(
                    "Delete Module",
                    key="DELETE",
                    size=(12, 1),
                    button_color=("white", "red"),
                ),
            )

        layout.append([sg.Column([[*buttons]], element_justification="center")])

        dialog = sg.Window(
            f"{'Edit' if is_edit else 'Add'} Module",
            layout,
            resizable=True,
            finalize=True,
            size=(600, 600),
        )

        while True:
            event, values = dialog.read()

            if event == sg.WIN_CLOSED or event == "CANCEL":
                dialog.close()
                return (None, predictions, "cancel")

            elif event == "ADD_TASK":
                module["name"] = values["MOD_NAME"]
                module["module_weight"] = validate_percent(
                    values["MOD_WEIGHT"], "Module weight"
                )
                if module["module_weight"] is not None:
                    dialog.close()
                    tasks.append({"score": 0.5, "weight": 0.0, "name": ""})
                    break

            elif event.startswith("DEL_TASK_"):
                task_idx = int(event.split("_")[2])
                module["name"] = values["MOD_NAME"]
                module["module_weight"] = validate_percent(
                    values["MOD_WEIGHT"], "Module weight"
                )
                if module["module_weight"] is not None:
                    dialog.close()
                    tasks.pop(task_idx)
                    break

            elif event == "MOD_COMPLETE":
                module["name"] = values["MOD_NAME"]
                module["is_complete"] = values["MOD_COMPLETE"]
                module["module_weight"] = validate_percent(
                    values["MOD_WEIGHT"], "Module weight"
                )
                if module["module_weight"] is not None:
                    dialog.close()
                    break

            elif event == "SAVE":
                module["name"] = values["MOD_NAME"].strip()
                module["is_complete"] = values["MOD_COMPLETE"]

                if not validate_module_name(module["name"], other_modules, None):
                    continue

                module["module_weight"] = validate_percent(
                    values["MOD_WEIGHT"], "Module weight"
                )
                if module["module_weight"] is None:
                    continue

                for i, task in enumerate(tasks):
                    score_val = validate_percent(
                        values[f"TASK_SCORE_{i}"], f"Task {i + 1} score"
                    )
                    weight_val = validate_percent(
                        values[f"TASK_WEIGHT_{i}"], f"Task {i + 1} weight"
                    )
                    if score_val is None or weight_val is None:
                        break
                    task["score"] = score_val
                    task["weight"] = weight_val
                    task["name"] = values[f"TASK_NAME_{i}"].strip()
                else:
                    if not validate_task_weights(tasks):
                        continue

                    module["tasks"] = tasks
                    _recompute_module(module)

                    if module["is_complete"]:
                        predictions.pop(old_name, None)
                    elif "PRED_SCORE" in values:
                        pred_str = values["PRED_SCORE"].strip()
                        if pred_str:
                            pred_val = validate_percent(pred_str, "Predicted score")
                            if pred_val is None:
                                continue
                            predictions[module["name"]] = pred_val
                        else:
                            predictions.pop(module["name"], None)

                    if old_name != module["name"] and old_name in predictions:
                        predictions[module["name"]] = predictions.pop(old_name)

                    dialog.close()
                    return (module, predictions, "save")

            elif event == "DELETE" and is_edit:
                if sg.popup_yes_no(
                    f"Delete module '{module['name']}'?", title="Confirm Delete"
                ) == "Yes":
                    dialog.close()
                    return (None, predictions, "delete")


def _do_save(modules: list, predictions: dict) -> None:
    """Compute stats and save to grades.json."""
    stats = compute_stats(modules, predictions)
    save_grades(
        GRADES_FILE,
        modules,
        predictions,
        stats["current"],
        TARGET,
        stats["required"],
    )


def _handle_add_module(modules: list, predictions: dict) -> tuple[list, dict, bool]:
    """Handle add module dialog. Returns (modules, predictions, changed)."""
    module, predictions, action = open_module_dialog(None, predictions, None, modules)
    if action == "save":
        modules.append(module)
        _do_save(modules, predictions)
        return (modules, predictions, True)
    return (modules, predictions, False)


def _handle_edit_module(
    idx: int, modules: list, predictions: dict
) -> tuple[list, dict, bool]:
    """Handle edit module dialog. Returns (modules, predictions, changed)."""
    old_module = modules[idx]
    module, predictions, action = open_module_dialog(old_module, predictions, idx, modules)

    if action == "save":
        modules[idx] = module
        _do_save(modules, predictions)
        return (modules, predictions, True)
    elif action == "delete":
        predictions.pop(old_module["name"], None)
        modules.pop(idx)
        _do_save(modules, predictions)
        return (modules, predictions, True)

    return (modules, predictions, False)


def run_gui() -> None:
    """Main GUI entry point."""
    sg.theme("LightGrey1")

    modules, predictions = [], {}
    if os.path.exists(GRADES_FILE):
        try:
            modules, predictions = load_grades(GRADES_FILE)
        except Exception as e:
            sg.popup_error(
                f"Could not load grades.json — starting fresh.\n\nError: {e}",
                title="Load Error",
            )

    window = make_main_window(modules, predictions)

    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, "Exit"):
            break

        elif event in ("ADD_MODULE", "ADD_MODULE_EMPTY"):
            window.hide()
            modules, predictions, _ = _handle_add_module(modules, predictions)
            window.close()
            window = make_main_window(modules, predictions)

        elif event and event.startswith("EDIT_"):
            idx = int(event.split("_")[1])
            window.hide()
            modules, predictions, _ = _handle_edit_module(idx, modules, predictions)
            window.close()
            window = make_main_window(modules, predictions)

    window.close()
