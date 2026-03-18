"""数据仓库 — Paper/DownloadTask/SearchHistory CRUD"""

from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

from cnki_downloader.models.download_task import TaskStatus
from cnki_downloader.models.paper import Paper

logger = logging.getLogger(__name__)


class PaperRepository:
    """文献数据CRUD。"""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def insert(self, paper: Paper) -> int:
        """插入文献，返回ID。若已存在(dbname+filename)则更新。"""
        cursor = await self._conn.execute(
            """INSERT INTO papers (title, authors, abstract, keywords, journal,
               publish_date, doi, url, dbname, filename, doc_type, local_path, is_favorite)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(dbname, filename) DO UPDATE SET
               title=excluded.title, authors=excluded.authors, abstract=excluded.abstract,
               url=excluded.url, local_path=excluded.local_path, updated_at=datetime('now')""",
            (
                paper.title,
                json.dumps(paper.authors, ensure_ascii=False),
                paper.abstract,
                json.dumps(paper.keywords, ensure_ascii=False),
                paper.journal,
                paper.publish_date,
                paper.doi,
                paper.url,
                paper.dbname,
                paper.filename,
                paper.doc_type,
                paper.local_path,
                int(paper.is_favorite),
            ),
        )
        await self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def get_by_id(self, paper_id: int) -> Paper | None:
        cursor = await self._conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,))
        row = await cursor.fetchone()
        return _row_to_paper(row) if row else None

    async def get_by_cnki_id(self, dbname: str, filename: str) -> Paper | None:
        cursor = await self._conn.execute(
            "SELECT * FROM papers WHERE dbname = ? AND filename = ?",
            (dbname, filename),
        )
        row = await cursor.fetchone()
        return _row_to_paper(row) if row else None

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Paper]:
        cursor = await self._conn.execute(
            "SELECT * FROM papers ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_paper(r) for r in rows]

    async def list_favorites(self) -> list[Paper]:
        cursor = await self._conn.execute(
            "SELECT * FROM papers WHERE is_favorite = 1 ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_paper(r) for r in rows]

    async def search_local(self, keyword: str) -> list[Paper]:
        """在本地数据库中搜索文献。"""
        pattern = f"%{keyword}%"
        cursor = await self._conn.execute(
            "SELECT * FROM papers WHERE title LIKE ? OR authors LIKE ? OR keywords LIKE ?",
            (pattern, pattern, pattern),
        )
        rows = await cursor.fetchall()
        return [_row_to_paper(r) for r in rows]

    async def update_local_path(self, paper_id: int, local_path: str) -> None:
        await self._conn.execute(
            "UPDATE papers SET local_path = ?, updated_at = datetime('now') WHERE id = ?",
            (local_path, paper_id),
        )
        await self._conn.commit()

    async def set_favorite(self, paper_id: int, favorite: bool) -> None:
        await self._conn.execute(
            "UPDATE papers SET is_favorite = ?, updated_at = datetime('now') WHERE id = ?",
            (int(favorite), paper_id),
        )
        await self._conn.commit()

    async def delete(self, paper_id: int) -> None:
        await self._conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        await self._conn.commit()

    async def count(self) -> int:
        cursor = await self._conn.execute("SELECT COUNT(*) FROM papers")
        row = await cursor.fetchone()
        return row[0] if row else 0


class DownloadTaskRepository:
    """下载任务CRUD。"""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def insert(self, paper_id: int | None, url: str) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO download_tasks (paper_id, url) VALUES (?, ?)",
            (paper_id, url),
        )
        await self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def update_status(
        self,
        task_id: int,
        status: TaskStatus,
        *,
        progress: float | None = None,
        downloaded_bytes: int | None = None,
        output_path: str | None = None,
        error_message: str | None = None,
    ) -> None:
        updates = ["status = ?", "updated_at = datetime('now')"]
        params: list[Any] = [status.value]

        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        if downloaded_bytes is not None:
            updates.append("downloaded_bytes = ?")
            params.append(downloaded_bytes)
        if output_path is not None:
            updates.append("output_path = ?")
            params.append(output_path)
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        params.append(task_id)
        await self._conn.execute(
            f"UPDATE download_tasks SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self._conn.commit()

    async def list_by_status(self, status: TaskStatus) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(
            "SELECT * FROM download_tasks WHERE status = ? ORDER BY created_at DESC",
            (status.value,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(
            "SELECT * FROM download_tasks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in await cursor.fetchall()]


class SearchHistoryRepository:
    """搜索历史CRUD。"""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def add(
        self, keyword: str, author: str = "", journal: str = "", result_count: int = 0
    ) -> None:
        await self._conn.execute(
            "INSERT INTO search_history (keyword, author, journal, result_count) "
            "VALUES (?, ?, ?, ?)",
            (keyword, author, journal, result_count),
        )
        await self._conn.commit()

    async def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(
            "SELECT * FROM search_history ORDER BY searched_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def clear(self) -> None:
        await self._conn.execute("DELETE FROM search_history")
        await self._conn.commit()


class TagRepository:
    """标签CRUD。"""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, name: str, color: str = "#808080") -> int:
        cursor = await self._conn.execute(
            "INSERT INTO tags (name, color) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET color=excluded.color",
            (name, color),
        )
        await self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def list_all(self) -> list[dict[str, Any]]:
        cursor = await self._conn.execute("SELECT * FROM tags ORDER BY name")
        return [dict(r) for r in await cursor.fetchall()]

    async def delete(self, tag_id: int) -> None:
        await self._conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        await self._conn.commit()

    async def add_to_paper(self, paper_id: int, tag_id: int) -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO paper_tags (paper_id, tag_id) VALUES (?, ?)",
            (paper_id, tag_id),
        )
        await self._conn.commit()

    async def remove_from_paper(self, paper_id: int, tag_id: int) -> None:
        await self._conn.execute(
            "DELETE FROM paper_tags WHERE paper_id = ? AND tag_id = ?",
            (paper_id, tag_id),
        )
        await self._conn.commit()

    async def get_paper_tags(self, paper_id: int) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(
            "SELECT t.* FROM tags t JOIN paper_tags pt ON t.id = pt.tag_id WHERE pt.paper_id = ?",
            (paper_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_papers_by_tag(self, tag_id: int) -> list[int]:
        cursor = await self._conn.execute(
            "SELECT paper_id FROM paper_tags WHERE tag_id = ?", (tag_id,)
        )
        return [row[0] for row in await cursor.fetchall()]


class CategoryRepository:
    """分类目录CRUD。"""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, name: str, parent_id: int | None = None) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO categories (name, parent_id) VALUES (?, ?)",
            (name, parent_id),
        )
        await self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def list_all(self) -> list[dict[str, Any]]:
        cursor = await self._conn.execute("SELECT * FROM categories ORDER BY sort_order, name")
        return [dict(r) for r in await cursor.fetchall()]

    async def delete(self, category_id: int) -> None:
        await self._conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await self._conn.commit()

    async def add_paper(self, paper_id: int, category_id: int) -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO paper_categories (paper_id, category_id) VALUES (?, ?)",
            (paper_id, category_id),
        )
        await self._conn.commit()

    async def remove_paper(self, paper_id: int, category_id: int) -> None:
        await self._conn.execute(
            "DELETE FROM paper_categories WHERE paper_id = ? AND category_id = ?",
            (paper_id, category_id),
        )
        await self._conn.commit()

    async def get_paper_categories(self, paper_id: int) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(
            "SELECT c.* FROM categories c "
            "JOIN paper_categories pc ON c.id = pc.category_id "
            "WHERE pc.paper_id = ?",
            (paper_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_papers_in_category(self, category_id: int) -> list[int]:
        cursor = await self._conn.execute(
            "SELECT paper_id FROM paper_categories WHERE category_id = ?", (category_id,)
        )
        return [row[0] for row in await cursor.fetchall()]


def _row_to_paper(row: aiosqlite.Row) -> Paper:
    """将数据库行转为Paper对象。"""
    return Paper(
        title=row["title"],
        authors=json.loads(row["authors"]) if row["authors"] else [],
        abstract=row["abstract"] or "",
        keywords=json.loads(row["keywords"]) if row["keywords"] else [],
        journal=row["journal"] or "",
        publish_date=row["publish_date"] or "",
        doi=row["doi"] or "",
        url=row["url"] or "",
        dbname=row["dbname"] or "",
        filename=row["filename"] or "",
        doc_type=row["doc_type"] or "pdf",
        local_path=row["local_path"] or "",
        is_favorite=bool(row["is_favorite"]),
    )
