"""数据模型单元测试"""

from cnki_downloader.models.download_task import DownloadTask, TaskStatus
from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult


class TestPaper:
    def test_cnki_id(self, sample_paper: Paper) -> None:
        assert sample_paper.cnki_id == "CJFDLAST_JSJX202401001"

    def test_cnki_id_empty(self) -> None:
        paper = Paper(title="test")
        assert paper.cnki_id == ""

    def test_short_info(self, sample_paper: Paper) -> None:
        info = sample_paper.short_info()
        assert "基于深度学习" in info
        assert "张三" in info
        assert "计算机学报" in info

    def test_short_info_many_authors(self) -> None:
        paper = Paper(title="test", authors=["A", "B", "C", "D", "E"])
        info = paper.short_info()
        assert "等" in info


class TestSearchResult:
    def test_has_more_true(self) -> None:
        query = SearchQuery(keyword="test", page_size=20)
        result = SearchResult(query=query, total_count=100, page=1)
        assert result.has_more is True

    def test_has_more_false(self) -> None:
        query = SearchQuery(keyword="test", page_size=20)
        result = SearchResult(query=query, total_count=10, page=1)
        assert result.has_more is False


class TestDownloadTask:
    def test_default_status(self) -> None:
        task = DownloadTask(task_id="t1", paper_title="test", url="http://x")
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0
