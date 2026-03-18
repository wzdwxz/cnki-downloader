"""下载 ViewModel — 管理下载任务状态"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from cnki_downloader.gui.workers.download_worker import DownloadWorker
from cnki_downloader.models.download_task import DownloadTask, TaskStatus
from cnki_downloader.models.paper import Paper
from cnki_downloader.utils.config import load_config


class DownloadViewModel(QObject):
    """下载视图模型。"""

    # 状态信号
    task_added = pyqtSignal(str, str)              # task_id, paper_title
    task_progress = pyqtSignal(str, int, int)      # task_id, downloaded, total
    task_completed = pyqtSignal(str, str)           # task_id, file_path
    task_error = pyqtSignal(str, str)               # task_id, error_msg
    all_completed = pyqtSignal(int, int)            # success_count, total_count

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tasks: dict[str, DownloadTask] = {}
        self._worker: DownloadWorker | None = None
        self._config = load_config()

    @property
    def tasks(self) -> dict[str, DownloadTask]:
        return self._tasks

    @property
    def output_dir(self) -> Path:
        return self._config.download_dir

    def download(self, papers: list[Paper], output_dir: Path | None = None) -> None:
        """开始下载文献列表。"""
        out = output_dir or self._config.download_dir

        # 注册任务
        for paper in papers:
            task_id = paper.filename or paper.title
            task = DownloadTask(
                task_id=task_id,
                paper_title=paper.title,
                url=paper.url,
                status=TaskStatus.PENDING,
            )
            self._tasks[task_id] = task
            self.task_added.emit(task_id, paper.title)

        self._worker = DownloadWorker(
            papers, out, max_concurrent=self._config.max_concurrent_downloads
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.file_completed.connect(self._on_file_completed)
        self._worker.file_error.connect(self._on_file_error)
        self._worker.all_finished.connect(self._on_all_finished)
        self._worker.error.connect(self._on_global_error)
        self._worker.start()

    def _on_progress(self, task_id: str, downloaded: int, total: int) -> None:
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = TaskStatus.DOWNLOADING
            task.downloaded_bytes = downloaded
            task.total_bytes = total
            task.progress = downloaded / total if total else 0.0
        self.task_progress.emit(task_id, downloaded, total)

    def _on_file_completed(self, task_id: str, file_path: str) -> None:
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.output_path = file_path
        self.task_completed.emit(task_id, file_path)

    def _on_file_error(self, task_id: str, error_msg: str) -> None:
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = TaskStatus.FAILED
            task.error_message = error_msg
        self.task_error.emit(task_id, error_msg)

    def _on_all_finished(self, paths: list[str]) -> None:
        success = len(paths)
        total = len(self._tasks)
        self.all_completed.emit(success, total)

    def _on_global_error(self, error_msg: str) -> None:
        self.task_error.emit("global", error_msg)
