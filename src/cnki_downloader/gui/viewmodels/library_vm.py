"""文献库 ViewModel — 管理文献列表、标签、分类、导出"""

from __future__ import annotations

import asyncio

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import (
    CategoryRepository,
    PaperRepository,
    TagRepository,
)
from cnki_downloader.models.paper import Paper


class LibraryLoadWorker(QThread):
    """后台加载文献库数据。"""

    finished = pyqtSignal(list, list, list, int)  # papers, tags, categories, total
    error = pyqtSignal(str)

    def __init__(self, keyword: str = "", favorites_only: bool = False, parent=None):
        super().__init__(parent)
        self._keyword = keyword
        self._favorites_only = favorites_only

    def run(self) -> None:
        try:
            result = asyncio.run(self._load())
            self.finished.emit(*result)
        except Exception as e:
            self.error.emit(str(e))

    async def _load(self):
        async with Database() as db:
            repo = PaperRepository(self._db_conn if hasattr(self, '_db_conn') else db.conn)
            tag_repo = TagRepository(db.conn)
            cat_repo = CategoryRepository(db.conn)

            if self._keyword:
                papers = await repo.search_local(self._keyword)
            elif self._favorites_only:
                papers = await repo.list_favorites()
            else:
                papers = await repo.list_all(limit=200)

            tags = await tag_repo.list_all()
            categories = await cat_repo.list_all()
            total = await repo.count()

            return papers, tags, categories, total


class LibraryViewModel(QObject):
    """文献库视图模型。"""

    papers_changed = pyqtSignal(list)
    tags_changed = pyqtSignal(list)
    categories_changed = pyqtSignal(list)
    total_changed = pyqtSignal(int)
    loading_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._papers: list[Paper] = []
        self._tags: list[dict] = []
        self._categories: list[dict] = []
        self._total: int = 0
        self._worker: LibraryLoadWorker | None = None

    @property
    def papers(self) -> list[Paper]:
        return self._papers

    @property
    def tags(self) -> list[dict]:
        return self._tags

    @property
    def categories(self) -> list[dict]:
        return self._categories

    def refresh(self, keyword: str = "", favorites_only: bool = False) -> None:
        """刷新文献库数据。"""
        self.loading_changed.emit(True)
        self._worker = LibraryLoadWorker(keyword, favorites_only)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, papers: list, tags: list, categories: list, total: int) -> None:
        self._papers = papers
        self._tags = tags
        self._categories = categories
        self._total = total
        self.loading_changed.emit(False)
        self.papers_changed.emit(self._papers)
        self.tags_changed.emit(self._tags)
        self.categories_changed.emit(self._categories)
        self.total_changed.emit(self._total)

    def _on_error(self, msg: str) -> None:
        self.loading_changed.emit(False)
        self.error_occurred.emit(msg)
