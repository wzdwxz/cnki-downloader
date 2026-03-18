"""搜索后台线程 — 在QThread中运行asyncio事件循环"""

from __future__ import annotations

import asyncio

from PyQt6.QtCore import QThread, pyqtSignal

from cnki_downloader.core.search import search
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.search_result import SearchQuery, SearchResult


class SearchWorker(QThread):
    """后台搜索线程。"""

    finished = pyqtSignal(SearchResult)
    error = pyqtSignal(str)

    def __init__(self, query: SearchQuery, parent=None) -> None:
        super().__init__(parent)
        self._query = query

    def run(self) -> None:
        try:
            result = asyncio.run(self._search())
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    async def _search(self) -> SearchResult:
        async with SessionManager() as session:
            return await search(session, self._query)
