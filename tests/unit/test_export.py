"""引用导出模块单元测试"""

from pathlib import Path

import pytest

from cnki_downloader.core.export import (
    _extract_year,
    _make_cite_key,
    export_bibtex,
    export_endnote,
    export_gbt7714,
    export_to_file,
)
from cnki_downloader.models.paper import Paper


@pytest.fixture
def papers() -> list[Paper]:
    return [
        Paper(
            title="基于深度学习的文本分类方法研究",
            authors=["张三", "李四"],
            journal="计算机学报",
            publish_date="2024-01-15",
            doi="10.1000/test.2024.001",
            keywords=["深度学习", "文本分类"],
            url="https://example.com/paper1",
        ),
        Paper(
            title="量子计算综述",
            authors=["王五", "赵六", "钱七", "孙八"],
            journal="物理学报",
            publish_date="2023-06",
        ),
    ]


class TestExportBibtex:
    def test_basic(self, papers: list[Paper]) -> None:
        result = export_bibtex(papers)
        assert "@article{" in result
        assert "基于深度学习" in result
        assert "张三 and 李四" in result
        assert "计算机学报" in result
        assert "2024" in result
        assert "10.1000/test.2024.001" in result

    def test_empty(self) -> None:
        assert export_bibtex([]) == ""

    def test_no_authors(self) -> None:
        result = export_bibtex([Paper(title="test")])
        assert "Unknown" in result


class TestExportEndnote:
    def test_basic(self, papers: list[Paper]) -> None:
        result = export_endnote(papers)
        assert "%0 Journal Article" in result
        assert "%T 基于深度学习" in result
        assert "%A 张三" in result
        assert "%J 计算机学报" in result
        assert "%D 2024" in result
        assert "%K 深度学习" in result


class TestExportGbt7714:
    def test_basic(self, papers: list[Paper]) -> None:
        result = export_gbt7714(papers)
        assert "[1]" in result
        assert "[2]" in result
        assert "张三, 李四" in result
        assert "[J]" in result
        assert "计算机学报" in result

    def test_many_authors(self, papers: list[Paper]) -> None:
        result = export_gbt7714(papers)
        # 第二篇有4个作者，应显示前3个+等
        assert "王五, 赵六, 钱七, 等" in result

    def test_no_authors(self) -> None:
        result = export_gbt7714([Paper(title="无名论文")])
        assert "佚名" in result


class TestExportToFile:
    def test_bibtex_file(self, papers: list[Paper], tmp_path: Path) -> None:
        out = tmp_path / "refs.bib"
        result = export_to_file(papers, out, "bibtex")
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "@article{" in content

    def test_endnote_file(self, papers: list[Paper], tmp_path: Path) -> None:
        out = tmp_path / "refs.enw"
        result = export_to_file(papers, out, "endnote")
        assert result.exists()

    def test_gbt7714_file(self, papers: list[Paper], tmp_path: Path) -> None:
        out = tmp_path / "refs.txt"
        result = export_to_file(papers, out, "gbt7714")
        assert result.exists()

    def test_invalid_format(self, papers: list[Paper], tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="不支持"):
            export_to_file(papers, tmp_path / "x.txt", "invalid")


class TestHelpers:
    def test_extract_year(self) -> None:
        assert _extract_year("2024-01-15") == "2024"
        assert _extract_year("2023-06") == "2023"
        assert _extract_year("") == ""
        assert _extract_year("no date") == ""

    def test_make_cite_key(self) -> None:
        paper = Paper(title="测试标题", authors=["作者"], publish_date="2024")
        key = _make_cite_key(paper)
        assert "2024" in key
        assert "作者" in key
