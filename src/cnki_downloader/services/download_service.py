"""下载服务 — 编排下载流程、管理任务状态"""

from __future__ import annotations

import logging
from pathlib import Path

from cnki_downloader.core.downloader import (
    ProgressCallback,
    batch_download,
    download_paper,
)
from cnki_downloader.core.session import SessionManager
from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import DownloadTaskRepository, PaperRepository
from cnki_downloader.models.download_task import TaskStatus
from cnki_downloader.models.paper import Paper
from cnki_downloader.utils.config import load_config

logger = logging.getLogger(__name__)


class DownloadService:
    """下载服务：管理下载任务、持久化状态。"""

    def __init__(self, session: SessionManager, db: Database) -> None:
        self._session = session
        self._db = db
        self._config = load_config()

    async def download_single(
        self,
        paper: Paper,
        output_dir: Path | None = None,
        progress: ProgressCallback | None = None,
    ) -> Path:
        """下载单篇文献。"""
        output_dir = output_dir or self._config.download_dir

        # 记录到数据库
        paper_repo = PaperRepository(self._db.conn)
        task_repo = DownloadTaskRepository(self._db.conn)

        paper_id = await paper_repo.insert(paper)
        task_id = await task_repo.insert(paper_id, paper.url)

        await task_repo.update_status(task_id, TaskStatus.DOWNLOADING)

        try:
            file_path = await download_paper(
                self._session, paper, output_dir, progress
            )

            # 更新数据库
            await paper_repo.update_local_path(paper_id, str(file_path))
            await task_repo.update_status(
                task_id,
                TaskStatus.COMPLETED,
                progress=1.0,
                output_path=str(file_path),
            )

            return file_path

        except Exception as e:
            await task_repo.update_status(
                task_id, TaskStatus.FAILED, error_message=str(e)
            )
            raise

    async def download_batch(
        self,
        papers: list[Paper],
        output_dir: Path | None = None,
        progress: ProgressCallback | None = None,
        max_concurrent: int | None = None,
    ) -> list[Path]:
        """批量下载文献。"""
        output_dir = output_dir or self._config.download_dir
        max_concurrent = max_concurrent or self._config.max_concurrent_downloads

        return await batch_download(
            self._session,
            papers,
            output_dir,
            progress,
            max_concurrent=max_concurrent,
            auto_convert=self._config.auto_convert_caj,
        )

    async def get_recent_tasks(self, limit: int = 50) -> list[dict]:
        repo = DownloadTaskRepository(self._db.conn)
        return await repo.list_recent(limit)

    async def get_failed_tasks(self) -> list[dict]:
        repo = DownloadTaskRepository(self._db.conn)
        return await repo.list_by_status(TaskStatus.FAILED)
