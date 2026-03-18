"""数据库集成测试 — 测试完整的文献管理工作流"""

from pathlib import Path

import pytest

from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import (
    CategoryRepository,
    DownloadTaskRepository,
    PaperRepository,
    SearchHistoryRepository,
    TagRepository,
)
from cnki_downloader.models.download_task import TaskStatus
from cnki_downloader.models.paper import Paper


@pytest.fixture
async def db(tmp_path: Path):
    database = Database(db_path=tmp_path / "integration_test.db")
    await database.connect()
    yield database
    await database.close()


class TestFullWorkflow:
    """测试完整的文献管理工作流：搜索 → 保存 → 标签 → 分类 → 导出。"""

    @pytest.mark.asyncio
    async def test_paper_lifecycle(self, db: Database) -> None:
        paper_repo = PaperRepository(db.conn)
        tag_repo = TagRepository(db.conn)
        cat_repo = CategoryRepository(db.conn)
        history_repo = SearchHistoryRepository(db.conn)

        # 1. 记录搜索历史
        await history_repo.add("深度学习", result_count=150)

        # 2. 保存搜索到的文献
        paper1_id = await paper_repo.insert(Paper(
            title="深度学习在自然语言处理中的应用",
            authors=["张三", "李四"],
            journal="计算机学报",
            publish_date="2024-01-15",
            dbname="CJFD",
            filename="DL_NLP_001",
            keywords=["深度学习", "NLP"],
        ))
        paper2_id = await paper_repo.insert(Paper(
            title="基于Transformer的文本生成方法",
            authors=["王五"],
            journal="软件学报",
            publish_date="2024-03-20",
            dbname="CJFD",
            filename="TRANS_001",
        ))

        assert await paper_repo.count() == 2

        # 3. 创建标签并标记文献
        tag_nlp_id = await tag_repo.create("NLP", "#ff6600")
        tag_dl_id = await tag_repo.create("深度学习", "#0066ff")

        await tag_repo.add_to_paper(paper1_id, tag_nlp_id)
        await tag_repo.add_to_paper(paper1_id, tag_dl_id)
        await tag_repo.add_to_paper(paper2_id, tag_nlp_id)

        p1_tags = await tag_repo.get_paper_tags(paper1_id)
        assert len(p1_tags) == 2

        nlp_papers = await tag_repo.get_papers_by_tag(tag_nlp_id)
        assert len(nlp_papers) == 2

        # 4. 创建分类目录并归类
        cat_cs_id = await cat_repo.create("计算机科学")
        cat_ai_id = await cat_repo.create("人工智能", parent_id=cat_cs_id)

        await cat_repo.add_paper(paper1_id, cat_ai_id)
        await cat_repo.add_paper(paper2_id, cat_ai_id)

        ai_papers = await cat_repo.get_papers_in_category(cat_ai_id)
        assert len(ai_papers) == 2

        # 5. 收藏文献
        await paper_repo.set_favorite(paper1_id, True)
        favorites = await paper_repo.list_favorites()
        assert len(favorites) == 1
        assert favorites[0].title == "深度学习在自然语言处理中的应用"

        # 6. 本地搜索
        results = await paper_repo.search_local("Transformer")
        assert len(results) == 1
        assert results[0].title == "基于Transformer的文本生成方法"

        # 7. 删除标签后验证
        await tag_repo.remove_from_paper(paper1_id, tag_nlp_id)
        p1_tags = await tag_repo.get_paper_tags(paper1_id)
        assert len(p1_tags) == 1

        # 8. 验证搜索历史
        history = await history_repo.list_recent()
        assert len(history) == 1
        assert history[0]["keyword"] == "深度学习"


class TestDownloadTaskWorkflow:
    """测试下载任务的完整状态流转。"""

    @pytest.mark.asyncio
    async def test_task_state_machine(self, db: Database) -> None:
        paper_repo = PaperRepository(db.conn)
        task_repo = DownloadTaskRepository(db.conn)

        # 创建文献和下载任务
        pid = await paper_repo.insert(Paper(
            title="测试文献",
            dbname="DB",
            filename="TEST_DL",
            url="https://example.com/paper.pdf",
        ))

        task_id = await task_repo.insert(pid, "https://example.com/paper.pdf")

        # pending → downloading
        await task_repo.update_status(task_id, TaskStatus.DOWNLOADING, progress=0.0)
        tasks = await task_repo.list_by_status(TaskStatus.DOWNLOADING)
        assert len(tasks) == 1

        # downloading → progress update
        await task_repo.update_status(
            task_id, TaskStatus.DOWNLOADING, progress=0.5, downloaded_bytes=512000
        )

        # downloading → completed
        await task_repo.update_status(
            task_id,
            TaskStatus.COMPLETED,
            progress=1.0,
            output_path="/downloads/test.pdf",
        )

        completed = await task_repo.list_by_status(TaskStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0]["output_path"] == "/downloads/test.pdf"

    @pytest.mark.asyncio
    async def test_task_failure(self, db: Database) -> None:
        task_repo = DownloadTaskRepository(db.conn)
        task_id = await task_repo.insert(None, "https://example.com/fail.pdf")

        await task_repo.update_status(task_id, TaskStatus.DOWNLOADING)
        await task_repo.update_status(
            task_id, TaskStatus.FAILED, error_message="Connection timeout"
        )

        failed = await task_repo.list_by_status(TaskStatus.FAILED)
        assert len(failed) == 1
        assert "timeout" in failed[0]["error_message"].lower()
