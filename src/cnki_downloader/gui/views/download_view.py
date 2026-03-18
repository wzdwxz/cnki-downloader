"""下载管理面板 — 任务列表、进度条、状态显示"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cnki_downloader.gui.viewmodels.download_vm import DownloadViewModel


class DownloadView(QWidget):
    """下载管理视图。"""

    def __init__(self, download_vm: DownloadViewModel, parent=None) -> None:
        super().__init__(parent)
        self._vm = download_vm
        self._progress_bars: dict[str, QProgressBar] = {}
        self._task_rows: dict[str, int] = {}
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题行
        header = QHBoxLayout()
        title = QLabel("下载管理")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        header.addWidget(title)
        header.addStretch()

        self._output_label = QLabel(f"保存至: {self._vm.output_dir}")
        self._output_label.setStyleSheet("color: #666; font-size: 12px;")
        header.addWidget(self._output_label)
        layout.addLayout(header)

        # 统计信息
        self._stats_label = QLabel("暂无下载任务")
        self._stats_label.setStyleSheet("color: #888; font-size: 13px;")
        layout.addWidget(self._stats_label)

        # 任务表格
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["文献", "进度", "大小", "状态"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 200)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 100)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, stretch=1)

    def _connect_signals(self) -> None:
        self._vm.task_added.connect(self._on_task_added)
        self._vm.task_progress.connect(self._on_task_progress)
        self._vm.task_completed.connect(self._on_task_completed)
        self._vm.task_error.connect(self._on_task_error)
        self._vm.all_completed.connect(self._on_all_completed)

    def _on_task_added(self, task_id: str, title: str) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._task_rows[task_id] = row

        self._table.setItem(row, 0, QTableWidgetItem(title))

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        self._table.setCellWidget(row, 1, progress_bar)
        self._progress_bars[task_id] = progress_bar

        self._table.setItem(row, 2, QTableWidgetItem("--"))

        status_item = QTableWidgetItem("等待中")
        status_item.setForeground(Qt.GlobalColor.gray)
        self._table.setItem(row, 3, status_item)

        self._update_stats()

    def _on_task_progress(self, task_id: str, downloaded: int, total: int) -> None:
        if task_id in self._progress_bars:
            pct = int(downloaded / total * 100) if total else 0
            self._progress_bars[task_id].setValue(pct)

        if task_id in self._task_rows:
            row = self._task_rows[task_id]
            size_text = _format_size(downloaded)
            if total:
                size_text += f" / {_format_size(total)}"
            self._table.setItem(row, 2, QTableWidgetItem(size_text))

            status_item = QTableWidgetItem("下载中")
            status_item.setForeground(Qt.GlobalColor.blue)
            self._table.setItem(row, 3, status_item)

    def _on_task_completed(self, task_id: str, file_path: str) -> None:
        if task_id in self._progress_bars:
            self._progress_bars[task_id].setValue(100)

        if task_id in self._task_rows:
            row = self._task_rows[task_id]
            status_item = QTableWidgetItem("已完成")
            status_item.setForeground(Qt.GlobalColor.darkGreen)
            self._table.setItem(row, 3, status_item)

        self._update_stats()

    def _on_task_error(self, task_id: str, error_msg: str) -> None:
        if task_id in self._task_rows:
            row = self._task_rows[task_id]
            status_item = QTableWidgetItem("失败")
            status_item.setForeground(Qt.GlobalColor.red)
            status_item.setToolTip(error_msg)
            self._table.setItem(row, 3, status_item)

        self._update_stats()

    def _on_all_completed(self, success: int, total: int) -> None:
        self._stats_label.setText(f"下载完成: {success}/{total} 篇成功")
        if success < total:
            QMessageBox.warning(
                self, "部分下载失败",
                f"共 {total} 篇文献，{success} 篇下载成功，{total - success} 篇失败。"
            )

    def _update_stats(self) -> None:
        tasks = self._vm.tasks
        if not tasks:
            self._stats_label.setText("暂无下载任务")
            return
        completed = sum(1 for t in tasks.values() if t.status.value == "completed")
        failed = sum(1 for t in tasks.values() if t.status.value == "failed")
        total = len(tasks)
        self._stats_label.setText(
            f"共 {total} 个任务 | 完成: {completed} | 失败: {failed}"
        )


def _format_size(bytes_count: int) -> str:
    """格式化文件大小。"""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    else:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
