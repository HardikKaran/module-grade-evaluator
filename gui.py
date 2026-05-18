import os
import io
import re
import textwrap
import PySimpleGUI as sg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from calculator import (
    compute_current,
    compute_prediction,
    compute_required,
    compute_required_after_predictions,
    compute_avg_required_incomplete,
    compute_classification_gaps,
    compute_degree_overall,
    compute_degree_classification,
)
from storage import GRADES_FILE, load_years, save_years, load_settings, save_settings

CARD_WIDTH = 1000


def _sort_years(years: list, active_idx: int) -> tuple[list, int]:
    if not years:
        return years, active_idx
    active_name = years[active_idx]["name"]

    def _key(y):
        m = re.search(r"\d+", y["name"])
        return (0, int(m.group())) if m else (1, y["name"])

    years = sorted(years, key=_key)
    new_idx = next((i for i, y in enumerate(years) if y["name"] == active_name), 0)
    return years, new_idx
CARD_GAP = 20


def compute_cols(window_width: int) -> int:
    """Compute number of columns that fit in window width."""
    return max(1, window_width // (CARD_WIDTH + CARD_GAP))


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def pct(decimal: float) -> str:
    return f"{decimal * 100:.1f}%"


def compute_stats(modules: list, predictions: dict, target: float) -> dict:
    current, remaining_weight = compute_current(modules)
    required = compute_required(current, remaining_weight, target)
    predicted = compute_prediction(modules, predictions) if predictions else None
    required_after = (
        compute_required_after_predictions(modules, predictions, target)
        if predictions
        else None
    )
    avg_required_incomplete = compute_avg_required_incomplete(modules, target)
    classification_gaps = compute_classification_gaps(current, remaining_weight)
    return {
        "current": current,
        "remaining_weight": remaining_weight,
        "required": required,
        "predicted": predicted,
        "required_after": required_after,
        "avg_required_incomplete": avg_required_incomplete,
        "classification_gaps": classification_gaps,
        "target": target,
    }


def _recompute_module(m: dict) -> dict:
    m["current_score"] = sum(t["score"] * t["weight"] for t in m["tasks"])
    entered = sum(t["weight"] for t in m["tasks"])
    m["remaining_fraction"] = 0.0 if m["is_complete"] else round(1.0 - entered, 10)
    return m


# ---------------------------------------------------------------------------
# Chart rendering
# ---------------------------------------------------------------------------

def render_module_chart_png(module: dict, predictions: dict, target: float = 0.70) -> bytes:
    """Render a bar chart for one module and return raw PNG bytes."""
    name = module["name"]
    pred_tasks = predictions.get(name, []) if not module["is_complete"] else []

    # Compute required score for remaining fraction
    obtained_contribution = module["current_score"]
    pred_contribution = sum(t["score"] * t["weight"] for t in pred_tasks)
    obtained_weight = sum(t["weight"] for t in module["tasks"])
    pred_weight = sum(t["weight"] for t in pred_tasks)
    remaining_weight = round(1.0 - obtained_weight - pred_weight, 10)

    required_score = None
    if remaining_weight > 1e-9:
        required_score = (target - obtained_contribution - pred_contribution) / remaining_weight

    # Collect bar data
    labels = []
    values = []
    colors = []

    for i, task in enumerate(module["tasks"]):
        task_label = task.get("name", "").strip() or f"Task {i + 1}"
        labels.append(textwrap.shorten(task_label, width=14, placeholder="…"))
        values.append(task["score"] * 100)
        colors.append("#4CAF50")  # green for obtained

    for pt in pred_tasks:
        pt_label = pt.get("name", "").strip() or "Predicted"
        labels.append(textwrap.shorten(pt_label, width=14, placeholder="…"))
        values.append(pt["score"] * 100)
        colors.append("#2196F3")  # blue for predicted

    if required_score is not None:
        labels.append("Required")
        values.append(max(0.0, required_score * 100))
        colors.append("#F44336" if required_score > 1.0 else "#FF9800")  # red if >100%, orange otherwise

    # Create figure
    fig, ax = plt.subplots(figsize=(9, 5), dpi=96)

    if not labels:
        ax.text(0.5, 0.5, "No data yet", ha="center", va="center", fontsize=14, transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
    else:
        bars = ax.bar(range(len(labels)), values, color=colors, edgecolor="black", linewidth=1.2)

        # Add bar labels
        ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=10)

        # Add target line
        ax.axhline(y=target * 100, color="red", linestyle="--", linewidth=2, label="Target (70%)")

        # Set labels and formatting
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Score (%)", fontsize=11, fontweight="bold")
        ax.set_ylim(0, max(110, max(values) * 1.15))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{int(y)}%"))

        # Legend
        obtained_patch = mpatches.Patch(facecolor="#4CAF50", label="Obtained", edgecolor="black")
        predicted_patch = mpatches.Patch(facecolor="#2196F3", label="Predicted", edgecolor="black")
        required_patch = mpatches.Patch(facecolor="#FF9800", label="Required", edgecolor="black")
        ax.legend(handles=[obtained_patch, predicted_patch, required_patch], loc="upper left", fontsize=9)

        ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=96)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def open_module_chart_popup(module: dict, predictions: dict, target: float = 0.70) -> None:
    """Open a modal popup showing the bar chart for one module."""
    png_bytes = render_module_chart_png(module, predictions, target)
    layout = [
        [sg.Text(module["name"], font=("Arial", 13, "bold"))],
        [sg.Image(data=png_bytes)],
        [sg.Button("Close", key="CLOSE_CHART", size=(10, 1))],
    ]
    win = sg.Window(
        f"Chart — {module['name']}",
        layout,
        modal=True,
        finalize=True,
    )
    while True:
        ev, _ = win.read()
        if ev in (sg.WIN_CLOSED, "CLOSE_CHART"):
            break
    win.close()


def render_year_chart_png(modules: list, predictions: dict, target: float = 0.70) -> bytes:
    """Render a grouped-bar overview chart for all modules and return PNG bytes."""
    if not modules:
        fig, ax = plt.subplots(figsize=(12, 6), dpi=96)
        ax.text(0.5, 0.5, "No modules yet", ha="center", va="center", fontsize=14, transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=96)
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    # Compute per-module scores
    module_names = [textwrap.shorten(m["name"], width=12, placeholder="…") for m in modules]
    obtained_scores = []
    predicted_scores = []
    required_scores = []

    for m in modules:
        # Obtained score (weighted sum)
        obtained = m["current_score"] * 100
        obtained_scores.append(obtained)

        # Predicted score (obtained + predicted weighted sum)
        pred_tasks = predictions.get(m["name"], []) if not m["is_complete"] else []
        pred_contribution = sum(t["score"] * t["weight"] for t in pred_tasks) * 100
        predicted_scores.append(obtained + pred_contribution)

        # Required score on remaining
        if m["is_complete"] or not pred_tasks:
            required_scores.append(None)
        else:
            obtained_weight = sum(t["weight"] for t in m["tasks"])
            pred_weight = sum(t["weight"] for t in pred_tasks)
            remaining_weight = round(1.0 - obtained_weight - pred_weight, 10)
            if remaining_weight > 1e-9:
                required = (target - m["current_score"] - sum(t["score"] * t["weight"] for t in pred_tasks)) / remaining_weight * 100
                required_scores.append(max(0.0, required))
            else:
                required_scores.append(None)

    # Create grouped bar chart
    fig, ax = plt.subplots(figsize=(12, 6), dpi=96)

    x = np.arange(len(module_names))
    bar_width = 0.25

    bars1 = ax.bar(x - bar_width, obtained_scores, bar_width, label="Obtained", color="#4CAF50", edgecolor="black")
    bars2 = ax.bar(x, predicted_scores, bar_width, label="Predicted", color="#2196F3", edgecolor="black")

    # Required bars (only for incomplete modules with remaining)
    required_values = [r if r is not None else 0 for r in required_scores]
    required_mask = [r is not None for r in required_scores]
    req_colors = ["#F44336" if (r is not None and r > 100) else "#FF9800" for r in required_scores]

    for i, (val, mask, color) in enumerate(zip(required_values, required_mask, req_colors)):
        if mask:
            ax.bar(i + bar_width, val, bar_width, color=color, edgecolor="black")

    # Formatting
    ax.set_xlabel("Module", fontsize=11, fontweight="bold")
    ax.set_ylabel("Score (%)", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(module_names, rotation=45, ha="right", fontsize=9)
    ax.set_ylim(0, max(110, max(obtained_scores + predicted_scores + required_values) * 1.1) if (obtained_scores or predicted_scores) else 110)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{int(y)}%"))
    ax.axhline(y=target * 100, color="red", linestyle="--", linewidth=2, label="Target (70%)")
    ax.grid(axis="y", alpha=0.3)

    # Legend
    obtained_patch = mpatches.Patch(facecolor="#4CAF50", label="Obtained", edgecolor="black")
    predicted_patch = mpatches.Patch(facecolor="#2196F3", label="Predicted", edgecolor="black")
    required_patch = mpatches.Patch(facecolor="#FF9800", label="Required", edgecolor="black")
    ax.legend(handles=[obtained_patch, predicted_patch, required_patch], loc="upper left", fontsize=10)

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=96)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def open_year_chart_popup(modules: list, predictions: dict, target: float = 0.70) -> None:
    """Open a modal popup showing the year-level overview chart."""
    png_bytes = render_year_chart_png(modules, predictions, target)
    layout = [
        [sg.Text("Year Overview", font=("Arial", 13, "bold"))],
        [sg.Image(data=png_bytes)],
        [sg.Button("Close", key="CLOSE_CHART", size=(10, 1))],
    ]
    win = sg.Window(
        "Year Chart",
        layout,
        modal=True,
        finalize=True,
    )
    while True:
        ev, _ = win.read()
        if ev in (sg.WIN_CLOSED, "CLOSE_CHART"):
            break
    win.close()


# ---------------------------------------------------------------------------
# Layout: stats bar
# ---------------------------------------------------------------------------

def build_stats_bar(stats: dict) -> sg.Frame:
    target = stats["target"]
    elements = [
        sg.Text(f"Current: {pct(stats['current'])}", font=("Arial", 12, "bold")),
        sg.VerticalSeparator(),
        sg.Text(f"Target: {pct(target)}", font=("Arial", 12)),
        sg.Button("Settings", key="SETTINGS", size=(8, 1), font=("Arial", 10)),
    ]

    if stats["predicted"] is not None:
        elements += [
            sg.VerticalSeparator(),
            sg.Text(f"Predicted: {pct(stats['predicted'])}", font=("Arial", 12)),
        ]

    elements.append(sg.VerticalSeparator())
    if stats["avg_required_incomplete"] is not None:
        color = "red" if stats["avg_required_incomplete"] > 1.0 else sg.theme_text_color()
        suffix = " (UNACHIEVABLE)" if stats["avg_required_incomplete"] > 1.0 else ""
        elements.append(
            sg.Text(
                f"Avg required (incomplete): {pct(stats['avg_required_incomplete'])}{suffix}",
                font=("Arial", 12),
                text_color=color,
            )
        )
    else:
        elements.append(sg.Text("All modules complete", font=("Arial", 12), text_color="green"))

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

    # Classification bands row
    gaps = stats.get("classification_gaps", {})
    band_elements = []
    for label, required in gaps.items():
        if required is None:
            band_elements.append(
                sg.Text(f"{label}: achieved", font=("Arial", 11), text_color="green")
            )
        elif required == float("inf") or required > 1.0:
            band_elements.append(
                sg.Text(f"{label}: N/A", font=("Arial", 11), text_color="red")
            )
        else:
            band_elements.append(
                sg.Text(f"{label}: need {pct(required)}", font=("Arial", 11))
            )
        band_elements.append(sg.VerticalSeparator())
    if band_elements:
        band_elements.pop()  # remove trailing separator

    rows = [[*elements]]
    if band_elements:
        rows.append([sg.Text("Classifications:", font=("Arial", 11, "bold")), sg.VerticalSeparator(), *band_elements])

    return sg.Frame("Year Statistics", rows, font=("Arial", 12, "bold"))


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
        # --- MANUAL PADDING ADJUSTMENTS ---
        # col_widths are in characters. Change these to tune column widths:
        COL_SCORE  = 3   # e.g. "100.0%" = 6 chars; add buffer
        COL_WEIGHT = 3   # same
        COL_STATUS = 5  # "Predicted" = 9 chars
        COL_TASK   = 10  # rest of space for task name; will truncate if too long
        # row_height: pixels per row — increase for more vertical spacing
        ROW_HEIGHT = 35
        # pad: ((left, right), (top, bottom)) — outer spacing of the table
        TABLE_PAD = (0, 10)
        # ----------------------------------

        rows.append(
            [
                sg.Table(
                    values=table_data,
                    headings=["Task", "Score", "Weight", "Status"],
                    col_widths=[COL_TASK, COL_SCORE, COL_WEIGHT, COL_STATUS],
                    auto_size_columns=False,
                    hide_vertical_scroll=True,
                    num_rows=len(table_data),
                    font=("Arial", 11),
                    header_font=("Arial", 11, "bold"),
                    pad=TABLE_PAD,
                    justification="left",
                    row_height=ROW_HEIGHT,
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

    rows.append([
        sg.Button("Edit Module", key=f"EDIT_{idx}", size=(12, 1)),
        sg.Button("View Chart", key=f"CHART_{idx}", size=(12, 1)),
    ])

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


def build_main_layout(years: list, active_idx: int, cols: int = 3) -> list:
    y = years[active_idx]
    modules, predictions, target = y["modules"], y.get("predictions", {}), y.get("target", 0.70)
    stats = compute_stats(modules, predictions, target)
    layout = [
        [*build_year_selector(years, active_idx)],
        [build_stats_bar(stats)],
        [sg.HorizontalSeparator()],
    ]
    if modules:
        layout.append([
            sg.Button("Add Module", key="ADD_MODULE", size=(15, 1)),
            sg.Button("Year Chart", key="YEAR_CHART", size=(12, 1)),
        ])
        layout.append([build_module_grid(modules, predictions, cols)])
    else:
        layout.append(
            [
                sg.Text("No modules yet. Click 'Add Module' to get started.", font=("Arial", 11)),
                sg.Button("Add Module", key="ADD_MODULE_EMPTY", size=(15, 1)),
            ]
        )
    return layout


def make_main_window(years: list, active_idx: int, size=None, cols: int = 3) -> sg.Window:
    layout = build_main_layout(years, active_idx, cols)
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

def _do_save(years: list, active_idx: int) -> None:
    for y in years:
        current, _ = compute_current(y["modules"])
        y["current_year_score"] = current
    save_years(GRADES_FILE, years, active_idx)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _handle_add_module(modules: list, predictions: dict):
    module, predictions, action = open_module_dialog(None, predictions, None, modules)
    if action == "save":
        modules.append(module)
        return modules, predictions, True
    return modules, predictions, False


def _handle_edit_module(idx: int, modules: list, predictions: dict):
    old_name = modules[idx]["name"]
    module, predictions, action = open_module_dialog(modules[idx], predictions, idx, modules)
    if action == "save":
        modules[idx] = module
        return modules, predictions, True
    elif action == "delete":
        predictions.pop(old_name, None)
        modules.pop(idx)
        return modules, predictions, True
    return modules, predictions, False


def open_theme_picker(current_theme: str) -> str | None:
    themes = sg.theme_list()
    default_idx = themes.index(current_theme) if current_theme in themes else 0
    layout = [
        [sg.Text("Select a theme:", font=("Arial", 12))],
        [sg.Listbox(themes, default_values=[themes[default_idx]], size=(30, 20),
                    key="THEME_LIST", font=("Arial", 11), enable_events=True)],
        [sg.Button("Apply", key="APPLY", size=(8, 1)), sg.Button("Cancel", key="CANCEL", size=(8, 1))],
    ]
    win = sg.Window("Choose Theme", layout, modal=True, finalize=True)
    result = None
    while True:
        ev, vals = win.read()
        if ev in (sg.WIN_CLOSED, "CANCEL"):
            break
        if ev in ("APPLY", "THEME_LIST"):
            selected = vals.get("THEME_LIST")
            if selected:
                result = selected[0]
            if ev == "APPLY":
                break
    win.close()
    return result if result and result != current_theme else None


def open_settings_popup(current_target: float) -> float | None:
    layout = [
        [sg.Text("Target Grade (%)", font=("Arial", 12))],
        [sg.Input(f"{current_target * 100:.1f}", key="TARGET_INPUT", size=(10, 1), font=("Arial", 12))],
        [sg.Button("Save", key="SAVE", size=(8, 1)), sg.Button("Cancel", key="CANCEL", size=(8, 1))],
    ]
    win = sg.Window("Settings", layout, modal=True, finalize=True)
    result = None
    while True:
        ev, vals = win.read()
        if ev in (sg.WIN_CLOSED, "CANCEL"):
            break
        if ev == "SAVE":
            try:
                v = float(vals["TARGET_INPUT"].strip())
                if v < 0 or v > 100:
                    sg.popup_error("Target must be between 0 and 100", title="Invalid Input")
                    continue
                result = v / 100.0
                break
            except ValueError:
                sg.popup_error("Target must be a number", title="Invalid Input")
    win.close()
    return result


# ---------------------------------------------------------------------------
# Multi-year dialogs
# ---------------------------------------------------------------------------

def open_degree_overview_popup(years: list) -> None:
    overall = compute_degree_overall(years)
    classification = compute_degree_classification(overall)

    rows = [[sg.Text("Degree Overview", font=("Arial", 13, "bold"))], [sg.HorizontalSeparator()]]
    for y in years:
        current, _ = compute_current(y["modules"])
        rows.append([
            sg.Text(
                f"{y['name']}  (weight: {pct(y['weight'])})  —  current: {pct(current)}",
                font=("Arial", 11),
            )
        ])
    rows += [
        [sg.HorizontalSeparator()],
        [sg.Text(f"Overall degree score: {pct(overall)}", font=("Arial", 12, "bold"))],
        [sg.Text(f"Projected classification: {classification}", font=("Arial", 12, "bold"))],
        [sg.Button("Close", key="CLOSE", size=(10, 1))],
    ]
    win = sg.Window("Degree Overview", rows, modal=True, finalize=True)
    while True:
        ev, _ = win.read()
        if ev in (sg.WIN_CLOSED, "CLOSE"):
            break
    win.close()


def open_manage_years_dialog(years: list, active_idx: int) -> tuple[list, int, bool]:
    """Dialog to add, rename, delete years and set weights. Returns (years, active_idx, changed)."""
    years = [y.copy() for y in years]
    changed = False

    while True:
        year_rows = []
        for i, y in enumerate(years):
            year_rows.append([
                sg.Input(y["name"], key=f"YN_{i}", size=(18, 1), font=("Arial", 11)),
                sg.Text("Weight %:", font=("Arial", 11)),
                sg.Input(f"{y['weight'] * 100:.1f}", key=f"YW_{i}", size=(8, 1), font=("Arial", 11)),
                sg.Button("Delete", key=f"DEL_YEAR_{i}", size=(8, 1), button_color=("white", "red"),
                          disabled=len(years) <= 1),
            ])

        layout = [
            [sg.Text("Manage Years", font=("Arial", 13, "bold"))],
            [sg.Text("Year weights should sum to 100%.", font=("Arial", 10), text_color="gray")],
            *year_rows,
            [sg.Button("Add Year", key="ADD_YEAR", size=(12, 1))],
            [sg.HorizontalSeparator()],
            [sg.Button("Save", key="SAVE", size=(10, 1)), sg.Button("Cancel", key="CANCEL", size=(10, 1))],
        ]
        win = sg.Window("Manage Years", layout, modal=True, finalize=True)

        while True:
            ev, vals = win.read()
            if ev in (sg.WIN_CLOSED, "CANCEL"):
                win.close()
                return years, active_idx, changed

            if ev == "ADD_YEAR":
                for i, y in enumerate(years):
                    y["name"] = vals[f"YN_{i}"].strip() or y["name"]
                    try:
                        y["weight"] = float(vals[f"YW_{i}"]) / 100
                    except ValueError:
                        pass
                years.append({"name": f"Year {len(years) + 1}", "weight": 0.0, "target": 0.70,
                              "modules": [], "predictions": {}})
                win.close()
                changed = True
                break

            if ev.startswith("DEL_YEAR_"):
                del_idx = int(ev.split("_")[2])
                if sg.popup_yes_no(f"Delete '{years[del_idx]['name']}'? Its modules will be lost.",
                                   title="Confirm Delete") == "Yes":
                    years.pop(del_idx)
                    if active_idx >= len(years):
                        active_idx = len(years) - 1
                    changed = True
                win.close()
                break

            if ev == "SAVE":
                new_years = []
                ok = True
                for i, y in enumerate(years):
                    name = vals[f"YN_{i}"].strip()
                    if not name:
                        sg.popup_error(f"Year {i + 1} name cannot be empty", title="Invalid Input")
                        ok = False
                        break
                    try:
                        w = float(vals[f"YW_{i}"])
                        if w < 0 or w > 100:
                            raise ValueError
                    except ValueError:
                        sg.popup_error(f"Year '{name}' weight must be 0–100", title="Invalid Input")
                        ok = False
                        break
                    new_years.append({**y, "name": name, "weight": w / 100})
                if not ok:
                    continue
                win.close()
                return new_years, active_idx, True


# ---------------------------------------------------------------------------
# Year selector row
# ---------------------------------------------------------------------------

def build_year_selector(years: list, active_idx: int) -> list:
    buttons = []
    for i, y in enumerate(years):
        if i == active_idx:
            btn_color = ("white", "#1976D2")
        else:
            btn_color = (sg.theme_text_color(), sg.theme_background_color())
        buttons.append(sg.Button(y["name"], key=f"YEAR_{i}", button_color=btn_color, font=("Arial", 11)))
    buttons += [
        sg.Button("+ Year", key="ADD_YEAR_BTN", size=(8, 1), font=("Arial", 10)),
        sg.Button("Manage Years", key="MANAGE_YEARS", size=(13, 1), font=("Arial", 10)),
        sg.Button("Degree Overview", key="DEGREE_OVERVIEW", size=(15, 1), font=("Arial", 10)),
        sg.Button("Theme", key="THEME_BTN", size=(8, 1), font=("Arial", 10)),
    ]
    return buttons


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _migrate_predictions(modules: list, predictions: dict) -> dict:
    for m in modules:
        name = m["name"]
        if name in predictions and isinstance(predictions[name], (int, float)):
            old_score = float(predictions[name])
            predictions[name] = [
                {"name": "Predicted", "score": old_score, "weight": m["remaining_fraction"]}
            ]
    return predictions


def run_gui() -> None:
    settings = load_settings()
    if settings.get("theme") not in sg.theme_list():
        settings["theme"] = "LightGrey1"
    sg.theme(settings["theme"])

    years = [{"name": "Year 1", "weight": 1.0, "target": 0.70, "modules": [], "predictions": {}}]
    active_idx = 0
    if os.path.exists(GRADES_FILE):
        try:
            years, active_idx = load_years(GRADES_FILE)
            for y in years:
                y["predictions"] = _migrate_predictions(y["modules"], y.get("predictions", {}))
            years, active_idx = _sort_years(years, active_idx)
        except Exception as e:
            sg.popup_error(f"Could not load grades.json — starting fresh.\n\nError: {e}", title="Load Error")

    current_cols = compute_cols(1600)
    window = make_main_window(years, active_idx, cols=current_cols)

    def rebuild(win, yrs, year_idx, cols_count):
        saved_size = win.size
        win.close()
        return make_main_window(yrs, year_idx, size=saved_size, cols=cols_count)

    def active_year():
        return years[active_idx]

    while True:
        event, _ = window.read(timeout=250)

        if event in (sg.WIN_CLOSED, "Exit"):
            break

        elif event == sg.TIMEOUT_EVENT:
            new_cols = compute_cols(window.size[0])
            if new_cols != current_cols:
                current_cols = new_cols
                window = rebuild(window, years, active_idx, current_cols)

        elif event and event.startswith("YEAR_") and event[5:].isdigit():
            active_idx = int(event[5:])
            window = rebuild(window, years, active_idx, current_cols)

        elif event == "SETTINGS":
            target = active_year().get("target", 0.70)
            new_target = open_settings_popup(target)
            if new_target is not None:
                active_year()["target"] = new_target
                _do_save(years, active_idx)
                window = rebuild(window, years, active_idx, current_cols)

        elif event in ("ADD_MODULE", "ADD_MODULE_EMPTY"):
            y = active_year()
            window.hide()
            mods, new_predictions, changed = _handle_add_module(y["modules"], y.get("predictions", {}))
            if changed:
                y["modules"], y["predictions"] = mods, new_predictions
                _do_save(years, active_idx)
            window = rebuild(window, years, active_idx, current_cols)

        elif event and event.startswith("EDIT_") and event[5:].isdigit():
            idx = int(event[5:])
            y = active_year()
            window.hide()
            mods, new_predictions, changed = _handle_edit_module(idx, y["modules"], y.get("predictions", {}))
            if changed:
                y["modules"], y["predictions"] = mods, new_predictions
                _do_save(years, active_idx)
            window = rebuild(window, years, active_idx, current_cols)

        elif event and event.startswith("CHART_") and event[6:].isdigit():
            idx = int(event[6:])
            y = active_year()
            open_module_chart_popup(y["modules"][idx], y.get("predictions", {}), y.get("target", 0.70))

        elif event == "YEAR_CHART":
            y = active_year()
            open_year_chart_popup(y["modules"], y.get("predictions", {}), y.get("target", 0.70))

        elif event in ("ADD_YEAR_BTN",):
            new_year = {"name": f"Year {len(years) + 1}", "weight": 0.0, "target": 0.70,
                        "modules": [], "predictions": {}}
            years.append(new_year)
            years, active_idx = _sort_years(years, len(years) - 1)
            _do_save(years, active_idx)
            window = rebuild(window, years, active_idx, current_cols)

        elif event == "MANAGE_YEARS":
            years, active_idx, changed = open_manage_years_dialog(years, active_idx)
            years, active_idx = _sort_years(years, active_idx)
            if changed:
                _do_save(years, active_idx)
            window = rebuild(window, years, active_idx, current_cols)

        elif event == "DEGREE_OVERVIEW":
            open_degree_overview_popup(years)

        elif event == "THEME_BTN":
            new_theme = open_theme_picker(settings.get("theme", "LightGrey1"))
            if new_theme is not None:
                settings["theme"] = new_theme
                save_settings(settings)
                sg.theme(new_theme)
                window = rebuild(window, years, active_idx, current_cols)

    window.close()
