"""Main window — wires the table, plots, summary panel, and persistence."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.model import Module, Task, Year
from src.storage import load, save
from src.widgets.module_table import ModuleTable
from src.widgets.plots import PlotTabs
from src.widgets.summary_panel import SummaryPanel

DEFAULT_PATH = Path("data/grades.json")


def _starter_year() -> Year:
    return Year(
        name="Year",
        target=70.0,
        modules=[
            Module(
                name="Sample module",
                credits=15.0,
                target=70.0,
                tasks=[
                    Task(name="Coursework", weight=0.4, score=75.0),
                    Task(name="Exam", weight=0.6, score=None),
                ],
            )
        ],
    )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Module Grade Evaluator")
        self.resize(1300, 820)

        # ---- model ----
        self._current_path: Path = DEFAULT_PATH
        if DEFAULT_PATH.exists():
            try:
                year = load(DEFAULT_PATH)
            except Exception:
                year = _starter_year()
        else:
            year = _starter_year()

        # ---- widgets ----
        self.table = ModuleTable(year)
        self.plots = PlotTabs()
        self.summary = SummaryPanel()

        # year header (year name + year target)
        header = QHBoxLayout()
        header.addWidget(QLabel("Year name:"))
        self.year_name = QLineEdit(year.name)
        self.year_name.textChanged.connect(self._on_year_name_changed)
        header.addWidget(self.year_name)
        header.addSpacing(20)
        header.addWidget(QLabel("Year target:"))
        self.year_target = QDoubleSpinBox()
        self.year_target.setRange(0.0, 100.0)
        self.year_target.setSuffix(" %")
        self.year_target.setSpecialValueText("none")
        self.year_target.setValue(year.target if year.target is not None else 0.0)
        self.year_target.valueChanged.connect(self._on_year_target_changed)
        header.addWidget(self.year_target)
        header.addStretch(1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(header)
        left_layout.addWidget(self.table)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.plots)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(8, 8, 8, 0)
        central_layout.addWidget(splitter, 1)
        central_layout.addWidget(self.summary)
        self.setCentralWidget(central)

        # ---- toolbar ----
        tb = QToolBar("Main")
        self.addToolBar(tb)
        act_add_module = QAction("Add module", self)
        act_add_module.triggered.connect(lambda: self.table.add_module())
        tb.addAction(act_add_module)
        act_add_task = QAction("Add task", self)
        act_add_task.triggered.connect(self.table.add_task_to_selected)
        tb.addAction(act_add_task)
        act_delete = QAction("Delete", self)
        act_delete.setShortcut(QKeySequence.Delete)
        act_delete.triggered.connect(self.table.delete_selected)
        tb.addAction(act_delete)
        tb.addSeparator()
        act_open = QAction("Open…", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._open)
        tb.addAction(act_open)
        act_save_as = QAction("Save As…", self)
        act_save_as.setShortcut(QKeySequence.SaveAs)
        act_save_as.triggered.connect(self._save_as)
        tb.addAction(act_save_as)
        act_new = QAction("New", self)
        act_new.triggered.connect(self._new)
        tb.addAction(act_new)

        # ---- wiring ----
        self.table.dataChanged_.connect(self._on_data_changed)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._autosave)

        # initial paint
        self._refresh_views()

    # ----- handlers -----

    def _on_data_changed(self) -> None:
        self._refresh_views()
        self._save_timer.start(500)

    def _on_year_name_changed(self, text: str) -> None:
        self.table.year().name = text or "Year"
        self._save_timer.start(500)

    def _on_year_target_changed(self, value: float) -> None:
        self.table.year().target = None if value == 0.0 else value
        self._refresh_views()
        self._save_timer.start(500)

    def _refresh_views(self) -> None:
        year = self.table.year()
        self.plots.refresh(year)
        self.summary.refresh(year)

    def _autosave(self) -> None:
        try:
            save(self.table.year(), self._current_path)
            self.summary.set_save_status(
                f"Saved to {self._current_path} at {time.strftime('%H:%M:%S')}"
            )
        except OSError as exc:
            self.summary.set_save_status(f"Save failed: {exc}")

    def _open(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open grades file", str(self._current_path), "JSON (*.json)"
        )
        if not path_str:
            return
        try:
            year = load(Path(path_str))
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._current_path = Path(path_str)
        self.year_name.blockSignals(True)
        self.year_name.setText(year.name)
        self.year_name.blockSignals(False)
        self.year_target.blockSignals(True)
        self.year_target.setValue(year.target if year.target is not None else 0.0)
        self.year_target.blockSignals(False)
        self.table.set_year(year)
        self._refresh_views()

    def _save_as(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save grades file", str(self._current_path), "JSON (*.json)"
        )
        if not path_str:
            return
        self._current_path = Path(path_str)
        self._autosave()

    def _new(self) -> None:
        if QMessageBox.question(
            self,
            "New file",
            "Discard current data and start a fresh year? (autosaves to default path)",
        ) != QMessageBox.Yes:
            return
        year = Year(name="Year", target=70.0, modules=[])
        self._current_path = DEFAULT_PATH
        self.year_name.blockSignals(True)
        self.year_name.setText(year.name)
        self.year_name.blockSignals(False)
        self.year_target.blockSignals(True)
        self.year_target.setValue(70.0)
        self.year_target.blockSignals(False)
        self.table.set_year(year)
        self._refresh_views()
