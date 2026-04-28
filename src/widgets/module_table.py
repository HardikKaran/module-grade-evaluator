"""Editable tree of modules and their tasks."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from src.model import Module, Task, Year, module_score, module_status

COL_NAME = 0
COL_CRED_OR_WEIGHT = 1
COL_TARGET_OR_SCORE = 2
COL_CURRENT = 3
COL_STATUS = 4

MODULE_ROLE = Qt.UserRole + 1
TASK_ROLE = Qt.UserRole + 2


def _fmt(v: Optional[float], suffix: str = "") -> str:
    return "" if v is None else f"{v:g}{suffix}"


def _parse_float(text: str) -> Optional[float]:
    text = (text or "").strip().rstrip("%")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class ModuleTable(QTreeWidget):
    """Tree view backed directly by a `Year` instance.

    Emits `dataChanged_` on any edit / structural change.
    """

    dataChanged_ = Signal()

    def __init__(self, year: Year, parent=None):
        super().__init__(parent)
        self._year = year
        self._suspend = False
        self.setHeaderLabels(
            ["Name", "Credits / Weight", "Target / Score", "Current %", "Status"]
        )
        self.setColumnWidth(COL_NAME, 200)
        self.setColumnWidth(COL_CRED_OR_WEIGHT, 130)
        self.setColumnWidth(COL_TARGET_OR_SCORE, 130)
        self.setColumnWidth(COL_CURRENT, 90)
        self.setAlternatingRowColors(True)
        self.itemChanged.connect(self._on_item_changed)
        self.rebuild()

    # ----- public API -----

    def year(self) -> Year:
        return self._year

    def set_year(self, year: Year) -> None:
        self._year = year
        self.rebuild()
        self.dataChanged_.emit()

    def add_module(self, name: str = "New module", credits: float = 15.0) -> None:
        m = Module(name=name, credits=credits, target=70.0, tasks=[])
        self._year.modules.append(m)
        self._append_module_item(m)
        self.dataChanged_.emit()

    def add_task_to_selected(self) -> None:
        item = self.currentItem()
        if item is None:
            if not self._year.modules:
                return
            module = self._year.modules[-1]
            module_item = self.topLevelItem(self.topLevelItemCount() - 1)
        else:
            module_item = item if item.parent() is None else item.parent()
            module = module_item.data(0, MODULE_ROLE)
        task = Task(name="New task", weight=0.0, score=None)
        module.tasks.append(task)
        self._append_task_item(module_item, task)
        module_item.setExpanded(True)
        self._refresh_module_row(module_item)
        self.dataChanged_.emit()

    def delete_selected(self) -> None:
        item = self.currentItem()
        if item is None:
            return
        parent = item.parent()
        if parent is None:
            module: Module = item.data(0, MODULE_ROLE)
            self._year.modules.remove(module)
            idx = self.indexOfTopLevelItem(item)
            self.takeTopLevelItem(idx)
        else:
            module: Module = parent.data(0, MODULE_ROLE)
            task: Task = item.data(0, TASK_ROLE)
            module.tasks.remove(task)
            parent.removeChild(item)
            self._refresh_module_row(parent)
        self.dataChanged_.emit()

    def rebuild(self) -> None:
        self._suspend = True
        self.clear()
        for m in self._year.modules:
            self._append_module_item(m)
        self._suspend = False

    # ----- internal -----

    def _append_module_item(self, module: Module) -> None:
        item = QTreeWidgetItem(self)
        item.setData(0, MODULE_ROLE, module)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        font = item.font(COL_NAME)
        font.setBold(True)
        item.setFont(COL_NAME, font)
        self._populate_module_row(item)
        for t in module.tasks:
            self._append_task_item(item, t)
        item.setExpanded(True)

    def _append_task_item(self, module_item: QTreeWidgetItem, task: Task) -> None:
        item = QTreeWidgetItem(module_item)
        item.setData(0, TASK_ROLE, task)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self._populate_task_row(item)

    def _populate_module_row(self, item: QTreeWidgetItem) -> None:
        self._suspend = True
        m: Module = item.data(0, MODULE_ROLE)
        item.setText(COL_NAME, m.name)
        item.setText(COL_CRED_OR_WEIGHT, _fmt(m.credits))
        item.setText(COL_TARGET_OR_SCORE, _fmt(m.target, "%"))
        score = module_score(m)
        item.setText(COL_CURRENT, _fmt(round(score, 1) if score is not None else None, "%"))
        item.setText(COL_STATUS, module_status(m))
        # read-only cells
        for col in (COL_CURRENT, COL_STATUS):
            item.setForeground(col, QBrush(QColor("#666")))
        self._suspend = False

    def _populate_task_row(self, item: QTreeWidgetItem) -> None:
        self._suspend = True
        t: Task = item.data(0, TASK_ROLE)
        item.setText(COL_NAME, t.name)
        item.setText(COL_CRED_OR_WEIGHT, _fmt(t.weight))
        item.setText(COL_TARGET_OR_SCORE, _fmt(t.score, "%"))
        item.setText(COL_CURRENT, "")
        item.setText(COL_STATUS, "")
        self._suspend = False

    def _refresh_module_row(self, item: QTreeWidgetItem) -> None:
        self._populate_module_row(item)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._suspend:
            return
        parent = item.parent()
        if parent is None:
            self._apply_module_edit(item, column)
        else:
            self._apply_task_edit(item, column)
            self._refresh_module_row(parent)
        self.dataChanged_.emit()

    def _apply_module_edit(self, item: QTreeWidgetItem, column: int) -> None:
        m: Module = item.data(0, MODULE_ROLE)
        text = item.text(column)
        if column == COL_NAME:
            m.name = text or "Module"
        elif column == COL_CRED_OR_WEIGHT:
            v = _parse_float(text)
            m.credits = v if v is not None else 0.0
        elif column == COL_TARGET_OR_SCORE:
            m.target = _parse_float(text)
        else:
            # read-only columns: revert
            self._populate_module_row(item)
            return
        # re-render row to normalise display
        self._populate_module_row(item)

    def _apply_task_edit(self, item: QTreeWidgetItem, column: int) -> None:
        t: Task = item.data(0, TASK_ROLE)
        text = item.text(column)
        if column == COL_NAME:
            t.name = text or "Task"
        elif column == COL_CRED_OR_WEIGHT:
            v = _parse_float(text)
            t.weight = v if v is not None else 0.0
        elif column == COL_TARGET_OR_SCORE:
            t.score = _parse_float(text)
        else:
            self._populate_task_row(item)
            return
        self._populate_task_row(item)
