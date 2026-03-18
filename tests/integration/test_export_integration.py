"""导出功能集成测试 — 测试从数据库读取并导出"""

from pathlib import Path

import pytest

from cnki_downloader.core.export import (
    export_bibtex,
    export_gbt7714,
    export_to_file,
)
from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import PaperRepository
from cnki_downloader.models.paper import Paper


@pytest.fixture
async def db_with_papers(tmp_path: Path):
    db = Database(db_path=tmp_path / "export_test.db")
    await db.connect()

    repo = PaperRepository(db.conn)
    await repo.insert(Paper(
        title="深度学习在图像识别中的应用研究",
        authors=["张三", "李四", "王五"],
        journal="计算机学报",
        publish_date="2024-01-15",
        doi="10.1000/test.001",
        keywords=["深度学习", "图像识别", "CNN"],
        dbname="CJFD",
        filename="IMG_001",
    ))
    await repo.insert(Paper(
        title="基于强化学习的机器人控制方法",
        authors=["赵六"],
        journal="自动化学报",
        publish_date="2023-11",
        dbname="CJFD",
        filename="RL_001",
    ))
    await repo.insert(Paper(
        title="量子计算在密码学中的应用前景",
        authors=["钱七", "孙八", "周九", "吴十"],
        journal="物理学报",
        publish_date="2024-05-01",
        doi="10.1000/test.002",
        dbname="CJFD",
        filename="QC_001",
    ))

    yield db, tmp_path
    await db.close()


class TestExportFromDatabase:
    @pytest.mark.asyncio
    async def test_export_all_bibtex(self, db_with_papers) -> None:
        db, tmp_path = db_with_papers
        repo = PaperRepository(db.conn)
        papers = await repo.list_all()

        out = tmp_path / "all_refs.bib"
        export_to_file(papers, out, "bibtex")

        content = out.read_text(encoding="utf-8")
        assert content.count("@article{") == 3
        assert "深度学习在图像识别" in content
        assert "强化学习" in content
        assert "量子计算" in content

    @pytest.mark.asyncio
    async def test_export_filtered_endnote(self, db_with_papers) -> None:
        db, tmp_path = db_with_papers
        repo = PaperRepository(db.conn)
        papers = await repo.search_local("深度学习")

        out = tmp_path / "filtered.enw"
        export_to_file(papers, out, "endnote")

        content = out.read_text(encoding="utf-8")
        assert "%T 深度学习在图像识别" in content
        assert "强化学习" not in content

    @pytest.mark.asyncio
    async def test_export_gbt7714_author_truncation(self, db_with_papers) -> None:
        db, tmp_path = db_with_papers
        repo = PaperRepository(db.conn)
        papers = await repo.list_all()

        result = export_gbt7714(papers)

        # 量子计算有4位作者，GB/T 7714应截断为3+等
        assert "钱七, 孙八, 周九, 等" in result
        # 深度学习有3位作者，不应截断
        assert "张三, 李四, 王五" in result

    @pytest.mark.asyncio
    async def test_bibtex_has_doi(self, db_with_papers) -> None:
        db, tmp_path = db_with_papers
        repo = PaperRepository(db.conn)
        papers = await repo.list_all()

        result = export_bibtex(papers)
        assert "10.1000/test.001" in result
        assert "10.1000/test.002" in result
