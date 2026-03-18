"""自定义进度条控件"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget


class DownloadProgressWidget(QWidget):
    """带标签的下载进度条。"""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self._title = title
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self._label = QLabel(title)
        self._label.setFixedWidth(200)
        self._label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        layout.addWidget(self._bar, stretch=1)

        self._size_label = QLabel("--")
        self._size_label.setFixedWidth(120)
        self._size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._size_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._size_label)

        self._status_label = QLabel("等待中")
        self._status_label.setFixedWidth(60)
        self._status_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self._status_label)

    def update_progress(self, downloaded: int, total: int) -> None:
        pct = int(downloaded / total * 100) if total else 0
        self._bar.setValue(pct)
        self._size_label.setText(f"{_fmt(downloaded)} / {_fmt(total)}")
        self._status_label.setText("下载中")
        self._status_label.setStyleSheet("color: #0d6efd; font-size: 12px;")

    def set_completed(self) -> None:
        self._bar.setValue(100)
        self._status_label.setText("完成")
        self._status_label.setStyleSheet("color: green; font-size: 12px;")

    def set_error(self, msg: str) -> None:
        self._status_label.setText("失败")
        self._status_label.setStyleSheet("color: red; font-size: 12px;")
        self._status_label.setToolTip(msg)


def _fmt(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 * 1024):.1f} MB"
