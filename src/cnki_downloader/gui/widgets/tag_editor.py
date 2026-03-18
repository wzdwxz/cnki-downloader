"""标签编辑控件（Phase 4完善）"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


class TagEditor(QWidget):
    """标签编辑器（占位）。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("标签功能开发中..."))
