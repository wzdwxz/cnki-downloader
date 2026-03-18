"""搜索服务 — 编排搜索流程、记录搜索历史"""

from __future__ import annotations

import logging

from cnki_downloader.core.search import search as core_search
from cnki_downloader.core.session import SessionManager
from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import PaperRepository, SearchHistoryRepository
from cnki_downloader.models.search_result import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class SearchService:
    """搜索服务：执行搜索、保存结果和历史。"""

    def __init__(self, session: SessionManager, db: Database) -> None:
        self._session = session
        self._db = db

    async def search(self, query: SearchQuery) -> SearchResult:
        """搜索知网并将结果保存到本地数据库。"""
        result = await core_search(self._session, query)

        # 记录搜索历史
        history_repo = SearchHistoryRepository(self._db.conn)
        await history_repo.add(
            keyword=query.keyword,
            author=query.author,
            journal=query.journal,
            result_count=result.total_count,
        )

        # 将搜索结果保存到数据库
        paper_repo = PaperRepository(self._db.conn)
        for paper in result.papers:
            if paper.dbname and paper.filename:
                await paper_repo.insert(paper)

        return result

    async def get_search_history(self, limit: int = 20) -> list[dict]:
        repo = SearchHistoryRepository(self._db.conn)
        return await repo.list_recent(limit)

    async def search_local(self, keyword: str):
        """在本地数据库搜索已保存的文献。"""
        repo = PaperRepository(self._db.conn)
        return await repo.search_local(keyword)
