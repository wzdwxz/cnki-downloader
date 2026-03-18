"""下载后台线程 — 在QThread中运行异步下载"""

from __future__ import annotations

import asyncio
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from cnki_downloader.core.downloader import (
    batch_download,
    download_paper,
)
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.paper import Paper


class DownloadWorker(QThread):
    """后台下载线程，支持单篇和批量下载。"""

    progress = pyqtSignal(str, int, int)           # task_id, downloaded, total
    file_completed = pyqtSignal(str, str)           # task_id, file_path
    file_error = pyqtSignal(str, str)               # task_id, error_msg
    all_finished = pyqtSignal(list)                  # list[str] 所有完成的路径
    error = pyqtSignal(str)

    def __init__(
        self,
        papers: list[Paper],
        output_dir: Path,
        max_concurrent: int = 3,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._papers = papers
        self._output_dir = output_dir
        self._max_concurrent = max_concurrent

    def run(self) -> None:
        try:
            paths = asyncio.run(self._download())
            self.all_finished.emit([str(p) for p in paths])
        except Exception as e:
            self.error.emit(str(e))

    async def _download(self) -> list[Path]:
        bridge = _ProgressBridge(self)
        async with SessionManager() as session:
            if len(self._papers) == 1:
                path = await download_paper(
                    session, self._papers[0], self._output_dir, bridge
                )
                return [path]
            else:
                return await batch_download(
                    session,
                    self._papers,
                    self._output_dir,
                    bridge,
                    max_concurrent=self._max_concurrent,
                )


class _ProgressBridge:
    """将下载进度转发到DownloadWorker的Qt信号。"""

    def __init__(self, worker: DownloadWorker) -> None:
        self._worker = worker

    def on_progress(self, task_id: str, downloaded: int, total: int) -> None:
        self._worker.progress.emit(task_id, downloaded, total)

    def on_complete(self, task_id: str, file_path: Path) -> None:
        self._worker.file_completed.emit(task_id, str(file_path))

    def on_error(self, task_id: str, error: Exception) -> None:
        self._worker.file_error.emit(task_id, str(error))
