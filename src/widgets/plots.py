"""Four matplotlib-based visualisation tabs."""
from __future__ import annotations

from typing import Optional

import matplotlib

matplotlib.use("QtAgg")  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.calc.required import required_per_module_for_year
from src.model import (
    CLASS_BOUNDARIES,
    Year,
    class_of,
    module_score,
    projected_module_score,
    year_score,
)


def _new_canvas() -> tuple[FigureCanvas, Figure]:
    fig = Figure(figsize=(6, 4), tight_layout=True)
    canvas = FigureCanvas(fig)
    return canvas, fig


def _draw_class_lines(ax) -> None:
    for threshold, label in CLASS_BOUNDARIES:
        ax.axhline(threshold, color="#999", linewidth=0.6, linestyle="--", zorder=0)
        ax.text(
            0.995,
            threshold,
            f" {label} ({threshold:g}) ",
            transform=ax.get_yaxis_transform(),
            ha="right",
            va="bottom",
            fontsize=7,
            color="#888",
        )


# --------------------------------------------------------------------------- #
# Tab 1 — Modules vs Targets
# --------------------------------------------------------------------------- #

class ModuleBarsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.canvas, self.fig = _new_canvas()
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        self.ax = self.fig.add_subplot(111)

    def refresh(self, year: Year) -> None:
        ax = self.ax
        ax.clear()
        names: list[str] = []
        scores: list[float] = []
        targets: list[Optional[float]] = []
        for m in year.modules:
            s = module_score(m)
            names.append(m.name)
            scores.append(0.0 if s is None else s)
            targets.append(m.target)
        if not names:
            ax.set_title("Add a module to see this chart")
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas.draw_idle()
            return
        x = list(range(len(names)))
        bars = ax.bar(x, scores, color="#4c78a8", zorder=2)
        for xi, t in zip(x, targets):
            if t is not None:
                ax.scatter(
                    [xi],
                    [t],
                    marker="D",
                    color="#e45756",
                    edgecolors="white",
                    s=70,
                    zorder=3,
                    label="Target" if xi == x[0] else None,
                )
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=20, ha="right")
        ax.set_ylim(0, 105)
        ax.set_ylabel("Score (%)")
        ax.set_title("Modules vs targets")
        _draw_class_lines(ax)
        for bar, score in zip(bars, scores):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{score:.1f}%" if score > 0 else "—",
                ha="center",
                va="bottom",
                fontsize=8,
            )
        if any(t is not None for t in targets):
            ax.legend(loc="upper right", fontsize=8)
        self.canvas.draw_idle()


# --------------------------------------------------------------------------- #
# Tab 2 — Credit-weighted donut
# --------------------------------------------------------------------------- #

class YearDonutTab(QWidget):
    def __init__(self):
        super().__init__()
        self.canvas, self.fig = _new_canvas()
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        self.ax = self.fig.add_subplot(111)

    def refresh(self, year: Year) -> None:
        ax = self.ax
        ax.clear()
        modules = [m for m in year.modules if m.credits > 0]
        if not modules:
            ax.set_title("Add modules with credits to see this chart")
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas.draw_idle()
            return
        sizes = [m.credits for m in modules]
        labels: list[str] = []
        for m in modules:
            s = module_score(m)
            label = f"{m.name}\n{m.credits:g} cr • {s:.1f}%" if s is not None else f"{m.name}\n{m.credits:g} cr • —"
            labels.append(label)
        wedges, _ = ax.pie(
            sizes,
            labels=labels,
            startangle=90,
            wedgeprops=dict(width=0.35, edgecolor="white"),
            textprops=dict(fontsize=8),
        )
        ys = year_score(year)
        center = f"{ys:.1f}%\n{class_of(ys)}" if ys is not None else "—"
        ax.text(0, 0, center, ha="center", va="center", fontsize=14, fontweight="bold")
        ax.set_title("Credit-weighted breakdown")
        self.canvas.draw_idle()


# --------------------------------------------------------------------------- #
# Tab 3 — What do I need?
# --------------------------------------------------------------------------- #

class WhatINeedTab(QWidget):
    def __init__(self):
        super().__init__()
        self._year: Optional[Year] = None

        top = QHBoxLayout()
        top.addWidget(QLabel("Year target:"))
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0.0, 100.0)
        self.target_spin.setSingleStep(1.0)
        self.target_spin.setValue(70.0)
        self.target_spin.setSuffix(" %")
        self.target_spin.valueChanged.connect(self._redraw)
        top.addWidget(self.target_spin)
        top.addStretch(1)

        self.canvas, self.fig = _new_canvas()
        self.ax = self.fig.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.canvas)

    def refresh(self, year: Year) -> None:
        self._year = year
        if year.target is not None:
            self.target_spin.blockSignals(True)
            self.target_spin.setValue(year.target)
            self.target_spin.blockSignals(False)
        self._redraw()

    def _redraw(self) -> None:
        ax = self.ax
        ax.clear()
        year = self._year
        if year is None or not year.modules:
            ax.set_title("Add modules to see this chart")
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas.draw_idle()
            return
        target = self.target_spin.value()
        per_module = required_per_module_for_year(year, target)
        names: list[str] = []
        values: list[float] = []
        colors: list[str] = []
        annotations: list[str] = []
        for m in year.modules:
            req = per_module.get(m.name)
            names.append(m.name)
            if req is None:
                values.append(0.0)
                colors.append("#cccccc")
                annotations.append("no weight/credits")
                continue
            if not req.has_remaining:
                values.append(0.0)
                colors.append("#9ec6e6")
                annotations.append("complete")
                continue
            if req.trivial:
                values.append(0.0)
                colors.append("#54a24b")
                annotations.append("achieved")
                continue
            display = max(0.0, min(req.value, 105.0))
            values.append(display)
            if not req.feasible:
                colors.append("#e45756")
                annotations.append(f"need {req.value:.1f}% (impossible)")
            elif req.value <= 80:
                colors.append("#54a24b")
                annotations.append(f"need {req.value:.1f}%")
            elif req.value <= 95:
                colors.append("#f1a93b")
                annotations.append(f"need {req.value:.1f}%")
            else:
                colors.append("#e45756")
                annotations.append(f"need {req.value:.1f}% (very tight)")
        x = list(range(len(names)))
        ax.bar(x, values, color=colors, zorder=2)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=20, ha="right")
        ax.set_ylim(0, 110)
        ax.set_ylabel("Required score on remaining (%)")
        ax.set_title(f"To hit {target:g}% year average")
        _draw_class_lines(ax)
        for xi, v, ann in zip(x, values, annotations):
            ax.text(xi, v + 1.5, ann, ha="center", va="bottom", fontsize=8)
        self.canvas.draw_idle()


# --------------------------------------------------------------------------- #
# Tab 4 — Sensitivity sliders
# --------------------------------------------------------------------------- #

class SensitivityTab(QWidget):
    def __init__(self):
        super().__init__()
        self._year: Optional[Year] = None
        self._sliders: list[tuple[int, int, QSlider, QLabel]] = []
        # buttons row
        button_row = QHBoxLayout()
        self.headline = QLabel("Year (projected): —")
        f = self.headline.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 2)
        self.headline.setFont(f)
        button_row.addWidget(self.headline)
        button_row.addStretch(1)
        for label, value in (("All 0", 0), ("All 50", 50), ("All 70", 70), ("All 100", 100)):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, v=value: self._set_all(v))
            button_row.addWidget(btn)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.slider_host = QWidget()
        self.slider_layout = QVBoxLayout(self.slider_host)
        self.slider_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.slider_host)

        self.canvas, self.fig = _new_canvas()
        self.ax = self.fig.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.canvas, 1)

    def refresh(self, year: Year) -> None:
        self._year = year
        self._rebuild_sliders()
        self._redraw()

    # --- internal ---

    def _clear_sliders(self) -> None:
        for _, _, slider, label in self._sliders:
            slider.setParent(None)
            label.setParent(None)
        # also clear any layout items (rows are nested layouts)
        while self.slider_layout.count():
            child = self.slider_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.setParent(None)
            else:
                lay = child.layout()
                if lay is not None:
                    while lay.count():
                        c = lay.takeAt(0)
                        if c.widget():
                            c.widget().setParent(None)
        self._sliders = []

    def _rebuild_sliders(self) -> None:
        self._clear_sliders()
        if self._year is None:
            return
        any_unentered = False
        for mi, m in enumerate(self._year.modules):
            for ti, t in enumerate(m.tasks):
                if t.score is not None:
                    continue
                any_unentered = True
                row = QHBoxLayout()
                name = QLabel(f"{m.name} — {t.name} (w {t.weight:g})")
                name.setMinimumWidth(260)
                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, 100)
                slider.setValue(70)
                value_label = QLabel("70%")
                value_label.setMinimumWidth(40)
                slider.valueChanged.connect(
                    lambda v, lbl=value_label: (lbl.setText(f"{v}%"), self._redraw())
                )
                row.addWidget(name)
                row.addWidget(slider, 1)
                row.addWidget(value_label)
                self.slider_layout.addLayout(row)
                self._sliders.append((mi, ti, slider, value_label))
        if not any_unentered:
            note = QLabel("All tasks have scores entered — nothing to slide.")
            note.setStyleSheet("color: #888;")
            self.slider_layout.addWidget(note)

    def _set_all(self, value: int) -> None:
        for _, _, slider, _ in self._sliders:
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        for _, _, slider, label in self._sliders:
            label.setText(f"{slider.value()}%")
        self._redraw()

    def _projected_year(self) -> Optional[float]:
        """Year score using slider values to fill in unentered tasks."""
        if self._year is None:
            return None
        slider_map = {(mi, ti): s.value() for mi, ti, s, _ in self._sliders}
        total_credits = 0.0
        weighted = 0.0
        for mi, m in enumerate(self._year.modules):
            if m.credits <= 0:
                continue
            tw = sum(t.weight for t in m.tasks)
            if tw <= 0:
                continue
            ms = 0.0
            for ti, t in enumerate(m.tasks):
                score = t.score
                if score is None:
                    score = float(slider_map.get((mi, ti), 0))
                ms += score * t.weight
            ms /= tw
            weighted += ms * m.credits
            total_credits += m.credits
        if total_credits <= 0:
            return None
        return weighted / total_credits

    def _redraw(self) -> None:
        score = self._projected_year()
        if score is None:
            self.headline.setText("Year (projected): —")
        else:
            self.headline.setText(
                f"Year (projected): {score:.2f}% ({class_of(score)})"
            )

        ax = self.ax
        ax.clear()
        if self._year is None or not self._year.modules:
            ax.set_title("Add modules to see this chart")
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas.draw_idle()
            return
        slider_map = {(mi, ti): s.value() for mi, ti, s, _ in self._sliders}
        names: list[str] = []
        actual: list[float] = []
        projected: list[float] = []
        for mi, m in enumerate(self._year.modules):
            names.append(m.name)
            cur = module_score(m)
            actual.append(cur if cur is not None else 0.0)
            tw = sum(t.weight for t in m.tasks)
            if tw <= 0:
                projected.append(0.0)
                continue
            ms = 0.0
            for ti, t in enumerate(m.tasks):
                score = t.score
                if score is None:
                    score = float(slider_map.get((mi, ti), 0))
                ms += score * t.weight
            projected.append(ms / tw)
        x = list(range(len(names)))
        width = 0.4
        ax.bar([xi - width / 2 for xi in x], actual, width, label="Current", color="#4c78a8")
        ax.bar([xi + width / 2 for xi in x], projected, width, label="Projected", color="#f1a93b")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=20, ha="right")
        ax.set_ylim(0, 105)
        ax.set_ylabel("Score (%)")
        ax.set_title("Current vs projected (sliders)")
        _draw_class_lines(ax)
        ax.legend(loc="upper right", fontsize=8)
        self.canvas.draw_idle()


# --------------------------------------------------------------------------- #
# Tab host
# --------------------------------------------------------------------------- #

class PlotTabs(QTabWidget):
    def __init__(self):
        super().__init__()
        self.modules_tab = ModuleBarsTab()
        self.donut_tab = YearDonutTab()
        self.what_i_need_tab = WhatINeedTab()
        self.sensitivity_tab = SensitivityTab()
        self.addTab(self.modules_tab, "Modules vs targets")
        self.addTab(self.donut_tab, "Year breakdown")
        self.addTab(self.what_i_need_tab, "What do I need?")
        self.addTab(self.sensitivity_tab, "Sensitivity")

    def refresh(self, year: Year) -> None:
        self.modules_tab.refresh(year)
        self.donut_tab.refresh(year)
        self.what_i_need_tab.refresh(year)
        self.sensitivity_tab.refresh(year)
