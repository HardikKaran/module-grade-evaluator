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
CARD_WIDTH = 1000
CARD_GAP = 20


def compute_cols(window_width: int) -> int:
    """Compute number of columns that fit in window width."""
    return max(1, window_width // (CARD_WIDTH + CARD_GAP))


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def pct(decimal: float) -> str:
    return f"{decimal * 100:.1f}%"


def compute_stats(modules: list, predictions: dict) -> dict:
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
    m["current_score"] = sum(t["score"] * t["weight"] for t in m["tasks"])
    entered = sum(t["weight"] for t in m["tasks"])
    m["remaining_fraction"] = 0.0 if m["is_complete"] else round(1.0 - entered, 10)
    return m


# ---------------------------------------------------------------------------
# Layout: stats bar
# ---------------------------------------------------------------------------

def build_stats_bar(stats: dict) -> sg.Frame:
    elements = [
        sg.Text(f"Current: {pct(stats['current'])}", font=("Arial", 12, "bold")),
        sg.VerticalSeparator(),
        sg.Text(f"Target: {pct(TARGET)}", font=("Arial", 12)),
    ]

    if stats["predicted"] is not None:
        elements += [
            sg.VerticalSeparator(),
            sg.Text(f"Predicted: {pct(stats['predicted'])}", font=("Arial", 12)),
        ]

    elements.append(sg.VerticalSeparator())
    if stats["required"] is not None:
        color = "red" if stats["required"] > 1.0 else sg.theme_text_color()
        suffix = " (UNACHIEVABLE)" if stats["required"] > 1.0 else ""
        elements.append(
            sg.Text(f"Required: {pct(stats['required'])}{suffix}", font=("Arial", 12), text_color=color)
        )
    else:
        if stats["current"] >= TARGET:
            elements.append(sg.Text("On track!", font=("Arial", 12), text_color="green"))
        else:
            elements.append(
                sg.Text("Below target, no remaining assessments", font=("Arial", 12), text_color="orange")
            )

    if stats["required_after"] is not None:
        color = "red" if stats["required_after"] > 1.0 else sg.theme_text_color()
        suffix = " (UNACHIEVABLE)" if stats["required_after"] > 1.0 else ""
        elements += [
            sg.VerticalSeparator(),
            sg.Text(
                f"After predictions: {pct(stats['required_after'])}{suffix}",
                font=("Arial", 12),
                text_color=color,
            ),
        ]

    return sg.Frame("Year Statistics", [[*elements]], font=("Arial", 12, "bold"))


# ---------------------------------------------------------------------------
# Layout: module card
# ---------------------------------------------------------------------------

def build_module_card(module: dict, predictions: dict, idx: int) -> sg.Frame:
    name = module["name"]
    is_complete = module["is_complete"]
    badge_text = "DONE" if is_complete else "IN PROGRESS"
    badge_bg = "green" if is_complete else "orange"

    pred_tasks = predictions.get(name, []) if not is_complete else []

    # Build table data: obtained tasks then predicted tasks
    table_data = []
    for i, task in enumerate(module["tasks"]):
        label = task.get("name", "").strip() or f"Task {i + 1}"
        table_data.append([label, pct(task["score"]), pct(task["weight"]), "Obtained"])
    for pt in pred_tasks:
        label = pt.get("name", "").strip() or "Predicted"
        table_data.append([label, pct(pt["score"]), pct(pt["weight"]), "Predicted"])

    rows = [
        [
            sg.Text(name, font=("Arial", 14, "bold")),
            sg.Text(
                badge_text,
                font=("Arial", 11),
                text_color="white",
                background_color=badge_bg,
                pad=(8, 0),
            ),
        ],
        [sg.Text(f"Weight toward year: {pct(module['module_weight'])}", font=("Arial", 11))],
    ]

    if table_data:
        rows.append(
            [
                sg.Table(
                    values=table_data,
                    headings=["Task", "Score", "Weight", "Status"],
                    col_widths=[5, 5, 5, 7],
                    auto_size_columns=False,
                    hide_vertical_scroll=True,
                    num_rows=len(table_data),
                    font=("Arial", 11),
                    header_font=("Arial", 11, "bold"),
                    pad=(0, 2),
                    justification="left",
                    row_height=35,
                    enable_events=False,
                )
            ]
        )
    else:
        rows.append([sg.Text("No tasks entered", font=("Arial", 11), text_color="gray")])

    rows.append(
        [sg.Text(f"Current score: {pct(module['current_score'])}", font=("Arial", 11, "bold"))]
    )

    if pred_tasks:
        predicted_total = module["current_score"] + sum(
            t["score"] * t["weight"] for t in pred_tasks
        )
        rows.append(
            [sg.Text(f"Predicted score: {pct(predicted_total)}", font=("Arial", 11))]
        )

    rows.append([sg.Button("Edit Module", key=f"EDIT_{idx}", size=(12, 1))])

    return sg.Frame("", rows, border_width=1, font=("Arial", 11), vertical_alignment="top", size=(1000, 400))


# ---------------------------------------------------------------------------
# Layout: module grid + main window
# ---------------------------------------------------------------------------

def build_module_grid(modules: list, predictions: dict, cols: int = 3) -> sg.Column:
    sorted_mods = (
        [(i, m) for i, m in enumerate(modules) if m["is_complete"]]
        + [(i, m) for i, m in enumerate(modules) if not m["is_complete"]]
    )
    cards = [build_module_card(m, predictions, i) for i, m in sorted_mods]

    # Pack cards into rows of cols columns
    layout = []
    for j in range(0, len(cards), cols):
        row_cards = cards[j : j + cols]
        layout.append(row_cards)

    return sg.Column(
        layout,
        scrollable=True,
        vertical_scroll_only=True,
        expand_x=True,
        expand_y=True,
        element_justification="left",
        vertical_alignment="top",
    )


def build_main_layout(modules: list, predictions: dict, cols: int = 3) -> list:
    stats = compute_stats(modules, predictions)
    layout = [
        [build_stats_bar(stats)],
        [sg.HorizontalSeparator()],
    ]
    if modules:
        layout.append([sg.Button("Add Module", key="ADD_MODULE", size=(15, 1))])
        layout.append([build_module_grid(modules, predictions, cols)])
    else:
        layout.append(
            [
                sg.Text("No modules yet. Click 'Add Module' to get started.", font=("Arial", 11)),
                sg.Button("Add Module", key="ADD_MODULE_EMPTY", size=(15, 1)),
            ]
        )
    return layout


def make_main_window(modules: list, predictions: dict, size=None, cols: int = 3) -> sg.Window:
    layout = build_main_layout(modules, predictions, cols)
    return sg.Window(
        "Module Grade Evaluator",
        layout,
        resizable=True,
        finalize=True,
        size=size or (1600, 950),
    )


# ---------------------------------------------------------------------------
# Dialog helpers: task row builders
# ---------------------------------------------------------------------------

def build_task_rows(tasks: list) -> list:
    """Input rows for obtained tasks."""
    rows = [
        [
            sg.Text("Name (opt.)", font=("Arial", 11), size=(20, 1)),
            sg.Text("Score %", font=("Arial", 11), size=(10, 1)),
            sg.Text("Weight %", font=("Arial", 11), size=(10, 1)),
            sg.Text("", size=(4, 1)),
        ]
    ]
    for i, task in enumerate(tasks):
        rows.append(
            [
                sg.Input(task.get("name", ""), key=f"TASK_NAME_{i}", size=(20, 1), font=("Arial", 11)),
                sg.Input(f"{task['score'] * 100:.1f}", key=f"TASK_SCORE_{i}", size=(10, 1), font=("Arial", 11)),
                sg.Input(f"{task['weight'] * 100:.1f}", key=f"TASK_WEIGHT_{i}", size=(10, 1), font=("Arial", 11)),
                sg.Button("X", key=f"DEL_TASK_{i}", size=(4, 1), button_color=("white", "red")),
            ]
        )
    return rows


def build_pred_task_rows(pred_tasks: list) -> list:
    """Input rows for predicted tasks."""
    rows = [
        [
            sg.Text("Name (opt.)", font=("Arial", 11), size=(20, 1)),
            sg.Text("Score %", font=("Arial", 11), size=(10, 1)),
            sg.Text("Weight %", font=("Arial", 11), size=(10, 1)),
            sg.Text("", size=(4, 1)),
        ]
    ]
    for i, pt in enumerate(pred_tasks):
        rows.append(
            [
                sg.Input(pt.get("name", ""), key=f"PT_NAME_{i}", size=(20, 1), font=("Arial", 11)),
                sg.Input(f"{pt['score'] * 100:.1f}", key=f"PT_SCORE_{i}", size=(10, 1), font=("Arial", 11)),
                sg.Input(f"{pt['weight'] * 100:.1f}", key=f"PT_WEIGHT_{i}", size=(10, 1), font=("Arial", 11)),
                sg.Button("X", key=f"DEL_PT_{i}", size=(4, 1), button_color=("white", "red")),
            ]
        )
    return rows


# ---------------------------------------------------------------------------
# Dialog helpers: snapshot (preserve state across rebuilds without validation)
# ---------------------------------------------------------------------------

def _snapshot(values: dict, module: dict, tasks: list, pred_tasks: list):
    """Read current dialog widget values into local state (no validation)."""
    module = module.copy()
    module["name"] = values.get("MOD_NAME", module["name"])
    module["is_complete"] = values.get("MOD_COMPLETE", module["is_complete"])
    try:
        module["module_weight"] = float(values.get("MOD_WEIGHT", "0")) / 100
    except (ValueError, TypeError):
        pass

    new_tasks = []
    for i, t in enumerate(tasks):
        nt = t.copy()
        nt["name"] = values.get(f"TASK_NAME_{i}", "")
        try:
            nt["score"] = float(values.get(f"TASK_SCORE_{i}", "0")) / 100
        except (ValueError, TypeError):
            pass
        try:
            nt["weight"] = float(values.get(f"TASK_WEIGHT_{i}", "0")) / 100
        except (ValueError, TypeError):
            pass
        new_tasks.append(nt)

    new_pred = []
    for i, pt in enumerate(pred_tasks):
        npt = pt.copy()
        npt["name"] = values.get(f"PT_NAME_{i}", "")
        try:
            npt["score"] = float(values.get(f"PT_SCORE_{i}", "0")) / 100
        except (ValueError, TypeError):
            pass
        try:
            npt["weight"] = float(values.get(f"PT_WEIGHT_{i}", "0")) / 100
        except (ValueError, TypeError):
            pass
        new_pred.append(npt)

    return module, new_tasks, new_pred


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_percent(val: str, field_name: str) -> float | None:
    try:
        v = float(val.strip())
        if v < 0 or v > 100:
            sg.popup_error(f"{field_name} must be between 0 and 100", title="Invalid Input")
            return None
        return v / 100.0
    except ValueError:
        sg.popup_error(f"{field_name} must be a number", title="Invalid Input")
        return None


def validate_module_name(name: str, other_modules: list) -> bool:
    if not name.strip():
        sg.popup_error("Module name cannot be empty", title="Invalid Input")
        return False
    for m in other_modules:
        if m["name"].lower() == name.lower():
            sg.popup_error("A module with that name already exists", title="Invalid Input")
            return False
    return True


def validate_weight_sum(items: list, label: str) -> bool:
    total = sum(t["weight"] for t in items)
    if total > 1.0 + 1e-9:
        sg.popup_error(f"{label} weights exceed 100% (total: {pct(total)})", title="Invalid Weights")
        return False
    return True


# ---------------------------------------------------------------------------
# Dialog: edit / add module
# ---------------------------------------------------------------------------

def open_module_dialog(
    module: dict | None, predictions: dict, idx: int | None, modules: list
) -> tuple[dict | None, dict, str]:
    """Open add/edit dialog. Returns (module_or_None, predictions, action)."""
    is_edit = module is not None
    module = (module or {
        "name": "",
        "tasks": [],
        "current_score": 0.0,
        "module_weight": 0.0,
        "is_complete": False,
        "remaining_fraction": 1.0,
    }).copy()

    tasks = [t.copy() for t in module["tasks"]]
    old_name = module["name"]
    pred_tasks = [pt.copy() for pt in predictions.get(old_name, [])]
    other_modules = [m for i, m in enumerate(modules) if i != idx]

    while True:
        is_complete = module["is_complete"]

        layout = [
            [
                sg.Frame(
                    "Module Details",
                    [
                        [sg.Text("Name:", font=("Arial", 12), size=(22, 1)),
                         sg.Input(module["name"], key="MOD_NAME", size=(30, 1), font=("Arial", 12))],
                        [sg.Text("Weight toward year (%):", font=("Arial", 12), size=(22, 1)),
                         sg.Input(f"{module['module_weight'] * 100:.1f}", key="MOD_WEIGHT", size=(10, 1), font=("Arial", 12))],
                        [sg.Checkbox("Module is complete", default=is_complete, key="MOD_COMPLETE", font=("Arial", 12))],
                    ],
                    font=("Arial", 12, "bold"),
                )
            ],
            [
                sg.Frame(
                    "Obtained Tasks",
                    [
                        *build_task_rows(tasks),
                        [sg.Button("Add Task", key="ADD_TASK", size=(14, 1))],
                    ],
                    font=("Arial", 12, "bold"),
                )
            ],
        ]

        if not is_complete:
            layout.append(
                [
                    sg.Frame(
                        "Predicted Tasks (for remaining assessment)",
                        [
                            *build_pred_task_rows(pred_tasks),
                            [sg.Button("Add Predicted Task", key="ADD_PT", size=(18, 1))],
                        ],
                        font=("Arial", 12, "bold"),
                    )
                ]
            )

        buttons = [sg.Button("Save", key="SAVE", size=(10, 1)), sg.Button("Cancel", key="CANCEL", size=(10, 1))]
        if is_edit:
            buttons.insert(1, sg.Button("Delete Module", key="DELETE", size=(14, 1), button_color=("white", "red")))
        layout.append([sg.Column([[*buttons]], element_justification="center")])

        dialog = sg.Window(
            f"{'Edit' if is_edit else 'Add'} Module",
            layout,
            resizable=True,
            finalize=True,
            size=(750, 800),
        )

        while True:
            event, values = dialog.read()

            if event in (sg.WIN_CLOSED, "CANCEL"):
                dialog.close()
                return (None, predictions, "cancel")

            elif event == "ADD_TASK":
                module, tasks, pred_tasks = _snapshot(values, module, tasks, pred_tasks)
                dialog.close()
                tasks.append({"score": 0.5, "weight": 0.0, "name": ""})
                break

            elif event.startswith("DEL_TASK_"):
                task_idx = int(event.split("_")[2])
                module, tasks, pred_tasks = _snapshot(values, module, tasks, pred_tasks)
                dialog.close()
                tasks.pop(task_idx)
                break

            elif event == "ADD_PT":
                module, tasks, pred_tasks = _snapshot(values, module, tasks, pred_tasks)
                dialog.close()
                pred_tasks.append({"score": 0.5, "weight": 0.0, "name": ""})
                break

            elif event.startswith("DEL_PT_"):
                pt_idx = int(event.split("_")[2])
                module, tasks, pred_tasks = _snapshot(values, module, tasks, pred_tasks)
                dialog.close()
                pred_tasks.pop(pt_idx)
                break

            elif event == "MOD_COMPLETE":
                module, tasks, pred_tasks = _snapshot(values, module, tasks, pred_tasks)
                module["is_complete"] = values["MOD_COMPLETE"]
                dialog.close()
                break

            elif event == "SAVE":
                name = values["MOD_NAME"].strip()
                if not validate_module_name(name, other_modules):
                    continue

                mod_weight = validate_percent(values["MOD_WEIGHT"], "Module weight")
                if mod_weight is None:
                    continue

                # Validate obtained tasks
                valid_tasks = []
                ok = True
                for i, t in enumerate(tasks):
                    score = validate_percent(values[f"TASK_SCORE_{i}"], f"Task {i+1} score")
                    weight = validate_percent(values[f"TASK_WEIGHT_{i}"], f"Task {i+1} weight")
                    if score is None or weight is None:
                        ok = False
                        break
                    valid_tasks.append({
                        "score": score,
                        "weight": weight,
                        "name": values[f"TASK_NAME_{i}"].strip(),
                    })
                if not ok:
                    continue
                if not validate_weight_sum(valid_tasks, "Obtained task"):
                    continue

                # Validate predicted tasks (only if not complete)
                valid_pred = []
                is_complete_now = values["MOD_COMPLETE"]
                if not is_complete_now:
                    for i, pt in enumerate(pred_tasks):
                        score = validate_percent(values[f"PT_SCORE_{i}"], f"Predicted task {i+1} score")
                        weight = validate_percent(values[f"PT_WEIGHT_{i}"], f"Predicted task {i+1} weight")
                        if score is None or weight is None:
                            ok = False
                            break
                        valid_pred.append({
                            "score": score,
                            "weight": weight,
                            "name": values[f"PT_NAME_{i}"].strip(),
                        })
                    if not ok:
                        continue

                    # Check predicted weights don't exceed remaining fraction
                    actual_remaining = round(1.0 - sum(t["weight"] for t in valid_tasks), 10)
                    pred_total = sum(t["weight"] for t in valid_pred)
                    if pred_total > actual_remaining + 1e-9:
                        sg.popup_error(
                            f"Predicted task weights ({pct(pred_total)}) exceed the remaining "
                            f"module fraction ({pct(actual_remaining)})",
                            title="Invalid Predicted Weights",
                        )
                        continue

                # Commit
                module["name"] = name
                module["module_weight"] = mod_weight
                module["is_complete"] = is_complete_now
                module["tasks"] = valid_tasks
                _recompute_module(module)

                # Migrate / update predictions
                if old_name in predictions and old_name != name:
                    predictions.pop(old_name, None)

                if is_complete_now:
                    predictions.pop(name, None)
                    predictions.pop(old_name, None)
                elif valid_pred:
                    predictions[name] = valid_pred
                else:
                    predictions.pop(name, None)
                    predictions.pop(old_name, None)

                dialog.close()
                return (module, predictions, "save")

            elif event == "DELETE" and is_edit:
                if sg.popup_yes_no(f"Delete module '{module['name']}'?", title="Confirm Delete") == "Yes":
                    dialog.close()
                    return (None, predictions, "delete")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _do_save(modules: list, predictions: dict) -> None:
    stats = compute_stats(modules, predictions)
    save_grades(GRADES_FILE, modules, predictions, stats["current"], TARGET, stats["required"])


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _handle_add_module(modules: list, predictions: dict):
    module, predictions, action = open_module_dialog(None, predictions, None, modules)
    if action == "save":
        modules.append(module)
        _do_save(modules, predictions)
        return modules, predictions, True
    return modules, predictions, False


def _handle_edit_module(idx: int, modules: list, predictions: dict):
    old_name = modules[idx]["name"]
    module, predictions, action = open_module_dialog(modules[idx], predictions, idx, modules)
    if action == "save":
        modules[idx] = module
        _do_save(modules, predictions)
        return modules, predictions, True
    elif action == "delete":
        predictions.pop(old_name, None)
        modules.pop(idx)
        _do_save(modules, predictions)
        return modules, predictions, True
    return modules, predictions, False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_gui() -> None:
    sg.theme("LightGrey1")

    modules, predictions = [], {}
    if os.path.exists(GRADES_FILE):
        try:
            modules, predictions = load_grades(GRADES_FILE)
            # Migrate old float predictions ({"ModName": 0.75}) to new list format
            for m in modules:
                name = m["name"]
                if name in predictions and isinstance(predictions[name], (int, float)):
                    old_score = float(predictions[name])
                    predictions[name] = [
                        {"name": "Predicted", "score": old_score, "weight": m["remaining_fraction"]}
                    ]
        except Exception as e:
            sg.popup_error(f"Could not load grades.json — starting fresh.\n\nError: {e}", title="Load Error")

    current_cols = compute_cols(1600)  # initial estimate
    window = make_main_window(modules, predictions, cols=current_cols)

    def rebuild(win, mods, preds, cols_count):
        """Save window size, close, rebuild, restore size."""
        saved_size = win.size
        win.close()
        new_win = make_main_window(mods, preds, size=saved_size, cols=cols_count)
        return new_win

    while True:
        event, _ = window.read(timeout=250)

        if event in (sg.WIN_CLOSED, "Exit"):
            break

        elif event == sg.TIMEOUT_EVENT:
            # Check if window width changed the column count
            new_cols = compute_cols(window.size[0])
            if new_cols != current_cols:
                current_cols = new_cols
                window = rebuild(window, modules, predictions, current_cols)

        elif event in ("ADD_MODULE", "ADD_MODULE_EMPTY"):
            window.hide()
            modules, predictions, _ = _handle_add_module(modules, predictions)
            window = rebuild(window, modules, predictions, current_cols)

        elif event and event.startswith("EDIT_"):
            idx = int(event.split("_")[1])
            window.hide()
            modules, predictions, _ = _handle_edit_module(idx, modules, predictions)
            window = rebuild(window, modules, predictions, current_cols)

    window.close()
