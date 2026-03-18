"""文献管理服务 — 收藏、分类、标签、导出"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from cnki_downloader.core.export import export_to_file
from cnki_downloader.core.library import Category, build_category_tree
from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import (
    CategoryRepository,
    PaperRepository,
    TagRepository,
)
from cnki_downloader.models.paper import Paper

logger = logging.getLogger(__name__)


class LibraryService:
    """文献管理服务：收藏、分类、标签、导出。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    # === 文献列表 ===

    async def list_papers(self, limit: int = 100, offset: int = 0) -> list[Paper]:
        repo = PaperRepository(self._db.conn)
        return await repo.list_all(limit, offset)

    async def list_favorites(self) -> list[Paper]:
        repo = PaperRepository(self._db.conn)
        return await repo.list_favorites()

    async def search_local(self, keyword: str) -> list[Paper]:
        repo = PaperRepository(self._db.conn)
        return await repo.search_local(keyword)

    async def get_paper_count(self) -> int:
        repo = PaperRepository(self._db.conn)
        return await repo.count()

    async def get_paper(self, paper_id: int) -> Paper | None:
        repo = PaperRepository(self._db.conn)
        return await repo.get_by_id(paper_id)

    async def delete_paper(self, paper_id: int) -> None:
        repo = PaperRepository(self._db.conn)
        await repo.delete(paper_id)

    # === 收藏 ===

    async def set_favorite(self, paper_id: int, favorite: bool) -> None:
        repo = PaperRepository(self._db.conn)
        await repo.set_favorite(paper_id, favorite)

    # === 标签 ===

    async def create_tag(self, name: str, color: str = "#808080") -> int:
        repo = TagRepository(self._db.conn)
        return await repo.create(name, color)

    async def list_tags(self) -> list[dict[str, Any]]:
        repo = TagRepository(self._db.conn)
        return await repo.list_all()

    async def delete_tag(self, tag_id: int) -> None:
        repo = TagRepository(self._db.conn)
        await repo.delete(tag_id)

    async def tag_paper(self, paper_id: int, tag_id: int) -> None:
        repo = TagRepository(self._db.conn)
        await repo.add_to_paper(paper_id, tag_id)

    async def untag_paper(self, paper_id: int, tag_id: int) -> None:
        repo = TagRepository(self._db.conn)
        await repo.remove_from_paper(paper_id, tag_id)

    async def get_paper_tags(self, paper_id: int) -> list[dict[str, Any]]:
        repo = TagRepository(self._db.conn)
        return await repo.get_paper_tags(paper_id)

    # === 分类 ===

    async def create_category(self, name: str, parent_id: int | None = None) -> int:
        repo = CategoryRepository(self._db.conn)
        return await repo.create(name, parent_id)

    async def list_categories(self) -> list[dict[str, Any]]:
        repo = CategoryRepository(self._db.conn)
        return await repo.list_all()

    async def get_category_tree(self) -> list[Category]:
        raw = await self.list_categories()
        cats = [
            Category(id=r["id"], name=r["name"], parent_id=r["parent_id"])
            for r in raw
        ]
        return build_category_tree(cats)

    async def delete_category(self, category_id: int) -> None:
        repo = CategoryRepository(self._db.conn)
        await repo.delete(category_id)

    async def categorize_paper(self, paper_id: int, category_id: int) -> None:
        repo = CategoryRepository(self._db.conn)
        await repo.add_paper(paper_id, category_id)

    async def uncategorize_paper(self, paper_id: int, category_id: int) -> None:
        repo = CategoryRepository(self._db.conn)
        await repo.remove_paper(paper_id, category_id)

    # === 导出 ===

    async def export_papers(
        self,
        paper_ids: list[int] | None,
        output_path: Path,
        fmt: str = "bibtex",
    ) -> Path:
        """导出指定文献的引用。paper_ids为None时导出全部。"""
        repo = PaperRepository(self._db.conn)
        if paper_ids:
            papers = []
            for pid in paper_ids:
                p = await repo.get_by_id(pid)
                if p:
                    papers.append(p)
        else:
            papers = await repo.list_all(limit=10000)

        return export_to_file(papers, output_path, fmt)
