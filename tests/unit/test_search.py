"""搜索模块单元测试"""

from cnki_downloader.core.search import _build_search_params, _parse_search_results
from cnki_downloader.models.search_result import SearchQuery


class TestBuildSearchParams:
    def test_basic_keyword(self) -> None:
        query = SearchQuery(keyword="深度学习")
        params = _build_search_params(query)
        assert params["txt_1_value1"] == "深度学习"
        assert params["DbPrefix"] == "SCDB"

    def test_with_author(self) -> None:
        query = SearchQuery(keyword="深度学习", author="张三")
        params = _build_search_params(query)
        assert params["txt_1_value1"] == "深度学习"
        assert params["txt_2_sel"] == "AU$%=|"
        assert params["txt_2_value1"] == "张三"

    def test_with_author_and_journal(self) -> None:
        query = SearchQuery(keyword="NLP", author="李四", journal="计算机学报")
        params = _build_search_params(query)
        assert params["txt_2_value1"] == "李四"
        assert params["txt_3_sel"] == "LY$%=|"
        assert params["txt_3_value1"] == "计算机学报"

    def test_with_date_range(self) -> None:
        query = SearchQuery(keyword="AI", start_date="2023-01-01", end_date="2024-12-31")
        params = _build_search_params(query)
        assert params["publishdate_from"] == "2023-01-01"
        assert params["publishdate_to"] == "2024-12-31"

    def test_no_date_keys_when_empty(self) -> None:
        query = SearchQuery(keyword="test")
        params = _build_search_params(query)
        assert "publishdate_from" not in params
        assert "publishdate_to" not in params


class TestParseSearchResults:
    def test_empty_html(self) -> None:
        papers, total = _parse_search_results("<html></html>")
        assert papers == []
        assert total == 0

    def test_no_table(self) -> None:
        html = '<html><span class="pagerTitleCell">找到 1,234 条结果</span></html>'
        papers, total = _parse_search_results(html)
        assert papers == []
        assert total == 1234

    def test_parse_result_row(self) -> None:
        link = "/kcms2/article/abstract?v=abc&dbname=CJFD&filename=TEST001"
        html = f"""
        <html>
        <span class="pagerTitleCell">找到 5 条结果</span>
        <table class="GridTableContent">
            <tr><th>序号</th><th>题名</th><th>作者</th><th>来源</th><th>发表时间</th></tr>
            <tr>
                <td>1</td>
                <td><a href="{link}">测试文献标题</a></td>
                <td><a>作者A</a><a>作者B</a></td>
                <td><a>测试期刊</a></td>
                <td>2024-01</td>
            </tr>
        </table>
        </html>
        """
        papers, total = _parse_search_results(html)
        assert total == 5
        assert len(papers) == 1
        p = papers[0]
        assert p.title == "测试文献标题"
        assert p.authors == ["作者A", "作者B"]
        assert p.journal == "测试期刊"
        assert p.publish_date == "2024-01"
        assert p.dbname == "CJFD"
        assert p.filename == "TEST001"
