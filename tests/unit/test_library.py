"""文献管理模块单元测试"""

from pathlib import Path

import pytest

from cnki_downloader.core.library import Category, build_category_tree
from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import (
    CategoryRepository,
    PaperRepository,
    TagRepository,
)
from cnki_downloader.models.paper import Paper


class TestBuildCategoryTree:
    def test_flat(self) -> None:
        cats = [
            Category(id=1, name="计算机"),
            Category(id=2, name="物理"),
        ]
        tree = build_category_tree(cats)
        assert len(tree) == 2

    def test_nested(self) -> None:
        cats = [
            Category(id=1, name="计算机"),
            Category(id=2, name="AI", parent_id=1),
            Category(id=3, name="NLP", parent_id=2),
        ]
        tree = build_category_tree(cats)
        assert len(tree) == 1
        assert tree[0].name == "计算机"
        assert len(tree[0].children) == 1
        assert tree[0].children[0].name == "AI"
        assert len(tree[0].children[0].children) == 1

    def test_empty(self) -> None:
        assert build_category_tree([]) == []


@pytest.fixture
async def db(tmp_path: Path):
    database = Database(db_path=tmp_path / "test.db")
    await database.connect()
    yield database
    await database.close()


class TestTagRepository:
    @pytest.mark.asyncio
    async def test_create_and_list(self, db: Database) -> None:
        repo = TagRepository(db.conn)
        tid = await repo.create("机器学习", "#ff0000")
        assert tid > 0

        tags = await repo.list_all()
        assert len(tags) == 1
        assert tags[0]["name"] == "机器学习"
        assert tags[0]["color"] == "#ff0000"

    @pytest.mark.asyncio
    async def test_upsert(self, db: Database) -> None:
        repo = TagRepository(db.conn)
        await repo.create("tag1", "#000000")
        await repo.create("tag1", "#ffffff")
        tags = await repo.list_all()
        assert len(tags) == 1
        assert tags[0]["color"] == "#ffffff"

    @pytest.mark.asyncio
    async def test_delete(self, db: Database) -> None:
        repo = TagRepository(db.conn)
        tid = await repo.create("to_delete")
        await repo.delete(tid)
        tags = await repo.list_all()
        assert len(tags) == 0

    @pytest.mark.asyncio
    async def test_paper_tagging(self, db: Database) -> None:
        paper_repo = PaperRepository(db.conn)
        tag_repo = TagRepository(db.conn)

        pid = await paper_repo.insert(Paper(title="论文1", dbname="DB", filename="T1"))
        tid = await tag_repo.create("标签1")

        await tag_repo.add_to_paper(pid, tid)
        paper_tags = await tag_repo.get_paper_tags(pid)
        assert len(paper_tags) == 1
        assert paper_tags[0]["name"] == "标签1"

        tagged_papers = await tag_repo.get_papers_by_tag(tid)
        assert pid in tagged_papers

        await tag_repo.remove_from_paper(pid, tid)
        paper_tags = await tag_repo.get_paper_tags(pid)
        assert len(paper_tags) == 0


class TestCategoryRepository:
    @pytest.mark.asyncio
    async def test_create_and_list(self, db: Database) -> None:
        repo = CategoryRepository(db.conn)
        cid = await repo.create("计算机科学")
        assert cid > 0

        cats = await repo.list_all()
        assert len(cats) == 1
        assert cats[0]["name"] == "计算机科学"

    @pytest.mark.asyncio
    async def test_nested_categories(self, db: Database) -> None:
        repo = CategoryRepository(db.conn)
        parent_id = await repo.create("理工科")
        child_id = await repo.create("计算机", parent_id=parent_id)

        cats = await repo.list_all()
        assert len(cats) == 2
        child = [c for c in cats if c["id"] == child_id][0]
        assert child["parent_id"] == parent_id

    @pytest.mark.asyncio
    async def test_paper_categorization(self, db: Database) -> None:
        paper_repo = PaperRepository(db.conn)
        cat_repo = CategoryRepository(db.conn)

        pid = await paper_repo.insert(Paper(title="论文1", dbname="DB", filename="C1"))
        cid = await cat_repo.create("分类1")

        await cat_repo.add_paper(pid, cid)
        paper_cats = await cat_repo.get_paper_categories(pid)
        assert len(paper_cats) == 1

        papers_in_cat = await cat_repo.get_papers_in_category(cid)
        assert pid in papers_in_cat

        await cat_repo.remove_paper(pid, cid)
        paper_cats = await cat_repo.get_paper_categories(pid)
        assert len(paper_cats) == 0

    @pytest.mark.asyncio
    async def test_delete(self, db: Database) -> None:
        repo = CategoryRepository(db.conn)
        cid = await repo.create("to_delete")
        await repo.delete(cid)
        cats = await repo.list_all()
        assert len(cats) == 0
