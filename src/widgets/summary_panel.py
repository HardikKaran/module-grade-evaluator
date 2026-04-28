"""Bottom-of-window summary: year average, class, target delta, save status."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from src.calc.required import required_for_year_uniform
from src.model import Year, class_of, year_score


class SummaryPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        left = QVBoxLayout()
        self.headline = QLabel("Year: —")
        f = self.headline.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        self.headline.setFont(f)
        self.detail = QLabel("Add modules and tasks to begin.")
        self.detail.setStyleSheet("color: #555;")
        left.addWidget(self.headline)
        left.addWidget(self.detail)

        self.save_label = QLabel("")
        self.save_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.save_label.setStyleSheet("color: #888;")

        layout.addLayout(left)
        layout.addStretch(1)
        layout.addWidget(self.save_label)

    def refresh(self, year: Year) -> None:
        score = year_score(year)
        if score is None:
            self.headline.setText("Year: —")
            self.detail.setText("Add modules and tasks to begin.")
            return
        cls = class_of(score)
        self.headline.setText(f"Year: {score:.2f}% ({cls})")

        if year.target is None:
            self.detail.setText(f"No year target set.")
            return
        delta = year.target - score
        if delta <= 0:
            self.detail.setText(
                f"Target {year.target:g}% — on track (+{-delta:.2f}% above target)."
            )
            return
        req = required_for_year_uniform(year, year.target)
        if req is None or not req.has_remaining:
            self.detail.setText(
                f"Target {year.target:g}% — short by {delta:.2f}% with no remaining work."
            )
            return
        feas = "needed" if req.feasible else "infeasible — would need >100%"
        self.detail.setText(
            f"Target {year.target:g}% — need ~{req.value:.1f}% on every remaining task ({feas})."
        )

    def set_save_status(self, text: str) -> None:
        self.save_label.setText(text)
