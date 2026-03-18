"""数据库模块单元测试"""

from pathlib import Path

import pytest

from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import (
    DownloadTaskRepository,
    PaperRepository,
    SearchHistoryRepository,
)
from cnki_downloader.models.download_task import TaskStatus
from cnki_downloader.models.paper import Paper


@pytest.fixture
async def db(tmp_path: Path):
    database = Database(db_path=tmp_path / "test.db")
    await database.connect()
    yield database
    await database.close()


class TestDatabase:
    @pytest.mark.asyncio
    async def test_connect_creates_tables(self, tmp_path: Path) -> None:
        db = Database(db_path=tmp_path / "test.db")
        await db.connect()
        # Verify tables exist by querying
        cursor = await db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        assert "papers" in tables
        assert "categories" in tables
        assert "tags" in tables
        assert "download_tasks" in tables
        assert "settings" in tables
        assert "search_history" in tables
        await db.close()


class TestPaperRepository:
    @pytest.mark.asyncio
    async def test_insert_and_get(self, db: Database) -> None:
        repo = PaperRepository(db.conn)
        paper = Paper(
            title="测试文献",
            authors=["张三", "李四"],
            journal="测试期刊",
            dbname="CJFD",
            filename="TEST001",
        )
        paper_id = await repo.insert(paper)
        assert paper_id > 0

        retrieved = await repo.get_by_cnki_id("CJFD", "TEST001")
        assert retrieved is not None
        assert retrieved.title == "测试文献"
        assert retrieved.authors == ["张三", "李四"]

    @pytest.mark.asyncio
    async def test_insert_upsert(self, db: Database) -> None:
        repo = PaperRepository(db.conn)
        paper = Paper(title="原始标题", dbname="CJFD", filename="TEST002")
        await repo.insert(paper)

        paper2 = Paper(title="更新标题", dbname="CJFD", filename="TEST002")
        await repo.insert(paper2)

        retrieved = await repo.get_by_cnki_id("CJFD", "TEST002")
        assert retrieved is not None
        assert retrieved.title == "更新标题"

    @pytest.mark.asyncio
    async def test_list_all(self, db: Database) -> None:
        repo = PaperRepository(db.conn)
        for i in range(3):
            await repo.insert(
                Paper(title=f"文献{i}", dbname="DB", filename=f"F{i}")
            )
        papers = await repo.list_all()
        assert len(papers) == 3

    @pytest.mark.asyncio
    async def test_search_local(self, db: Database) -> None:
        repo = PaperRepository(db.conn)
        await repo.insert(Paper(title="深度学习综述", dbname="DB", filename="DL1"))
        await repo.insert(Paper(title="量子计算", dbname="DB", filename="QC1"))

        results = await repo.search_local("深度学习")
        assert len(results) == 1
        assert results[0].title == "深度学习综述"

    @pytest.mark.asyncio
    async def test_set_favorite(self, db: Database) -> None:
        repo = PaperRepository(db.conn)
        paper_id = await repo.insert(Paper(title="收藏测试", dbname="DB", filename="FAV1"))
        await repo.set_favorite(paper_id, True)

        favorites = await repo.list_favorites()
        assert len(favorites) == 1

    @pytest.mark.asyncio
    async def test_count(self, db: Database) -> None:
        repo = PaperRepository(db.conn)
        assert await repo.count() == 0
        await repo.insert(Paper(title="test", dbname="DB", filename="C1"))
        assert await repo.count() == 1

    @pytest.mark.asyncio
    async def test_delete(self, db: Database) -> None:
        repo = PaperRepository(db.conn)
        pid = await repo.insert(Paper(title="to_delete", dbname="DB", filename="D1"))
        await repo.delete(pid)
        assert await repo.count() == 0


class TestDownloadTaskRepository:
    @pytest.mark.asyncio
    async def test_insert_and_update(self, db: Database) -> None:
        repo = DownloadTaskRepository(db.conn)
        task_id = await repo.insert(paper_id=None, url="https://example.com/test.pdf")
        assert task_id > 0

        await repo.update_status(task_id, TaskStatus.DOWNLOADING, progress=0.5)
        await repo.update_status(
            task_id, TaskStatus.COMPLETED, progress=1.0, output_path="/tmp/test.pdf"
        )

        tasks = await repo.list_by_status(TaskStatus.COMPLETED)
        assert len(tasks) == 1
        assert tasks[0]["output_path"] == "/tmp/test.pdf"

    @pytest.mark.asyncio
    async def test_list_recent(self, db: Database) -> None:
        repo = DownloadTaskRepository(db.conn)
        for i in range(5):
            await repo.insert(paper_id=None, url=f"https://example.com/{i}.pdf")
        tasks = await repo.list_recent(limit=3)
        assert len(tasks) == 3


class TestSearchHistoryRepository:
    @pytest.mark.asyncio
    async def test_add_and_list(self, db: Database) -> None:
        repo = SearchHistoryRepository(db.conn)
        await repo.add("机器学习", result_count=100)
        await repo.add("深度学习", author="张三", result_count=50)

        history = await repo.list_recent()
        assert len(history) == 2
        keywords = {h["keyword"] for h in history}
        assert "机器学习" in keywords
        assert "深度学习" in keywords

    @pytest.mark.asyncio
    async def test_clear(self, db: Database) -> None:
        repo = SearchHistoryRepository(db.conn)
        await repo.add("test")
        await repo.clear()
        history = await repo.list_recent()
        assert len(history) == 0
