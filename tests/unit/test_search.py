"""搜索模块单元测试"""

from unittest.mock import AsyncMock, patch

import pytest

from cnki_downloader.core.exceptions import CaptchaRequiredError, SearchError
from cnki_downloader.core.search import (
    SOURCE_TYPE_CODES,
    _build_search_url,
    search,
)
from cnki_downloader.models.search_result import SearchQuery


class TestBuildSearchUrl:
    def test_basic_keyword(self) -> None:
        query = SearchQuery(keyword="深度学习")
        url = _build_search_url(query)
        assert "kw=" in url
        assert "%E6%B7%B1%E5%BA%A6%E5%AD%A6%E4%B9%A0" in url  # URL-encoded 深度学习
        assert "korder=SU" in url

    def test_multiple_keywords(self) -> None:
        query = SearchQuery(keyword="深度学习", extra_keywords=["自然语言处理"])
        url = _build_search_url(query)
        # 多关键词以空格分隔（URL编码为+或%20）
        assert "kw=" in url

    def test_with_date_range(self) -> None:
        query = SearchQuery(keyword="AI", start_date="2023-01-01", end_date="2024-12-31")
        url = _build_search_url(query)
        assert "date_from=2023" in url
        assert "date_to=2024" in url

    def test_no_date_in_url_when_empty(self) -> None:
        query = SearchQuery(keyword="test")
        url = _build_search_url(query)
        assert "date_from" not in url
        assert "date_to" not in url

    def test_with_source_types_code(self) -> None:
        query = SearchQuery(keyword="test", source_types="CJFQ")
        url = _build_search_url(query)
        assert "bCKY3=CJFQ" in url

    def test_with_source_types_chinese(self) -> None:
        query = SearchQuery(keyword="test", source_types="期刊")
        url = _build_search_url(query)
        assert "bCKY3=CJFQ" in url

    def test_with_author(self) -> None:
        query = SearchQuery(keyword="AI", author="张三")
        url = _build_search_url(query)
        assert "au=" in url

    def test_with_journal(self) -> None:
        query = SearchQuery(keyword="AI", journal="计算机学报")
        url = _build_search_url(query)
        assert "base=" in url

    def test_uses_detected_endpoints(self) -> None:
        """验证搜索 URL 使用自动探测的端点。"""
        with patch(
            "cnki_downloader.core.search.get_current_endpoints",
            return_value={
                "version": "kns9",
                "search_url": "https://kns.cnki.net/kns9/defaultresult/index",
            },
        ):
            query = SearchQuery(keyword="test")
            url = _build_search_url(query)
            assert url.startswith("https://kns.cnki.net/kns9/defaultresult/index")


class TestSourceTypeCodes:
    def test_known_types(self) -> None:
        assert SOURCE_TYPE_CODES["期刊"] == "CJFQ"
        assert SOURCE_TYPE_CODES["博士"] == "CDFD"
        assert SOURCE_TYPE_CODES["硕士"] == "CMFD"

    def test_composite_type(self) -> None:
        assert SOURCE_TYPE_CODES["学位论文"] == "CDFD,CMFD"


@pytest.mark.asyncio
async def test_search_reraises_captcha_required_error() -> None:
    """验证 CaptchaRequiredError 被正确抛出而非被包装为 SearchError。"""
    session = AsyncMock()

    with patch(
        "cnki_downloader.core.api_probe.ensure_api_endpoints",
        new_callable=AsyncMock,
    ), patch(
        "cnki_downloader.core.search._browser_search",
        side_effect=CaptchaRequiredError("需要验证码"),
    ):
        with pytest.raises(CaptchaRequiredError, match="需要验证码"):
            await search(session, SearchQuery(keyword="test"))


@pytest.mark.asyncio
async def test_search_wraps_generic_error_as_search_error() -> None:
    """验证一般异常被包装为 SearchError。"""
    session = AsyncMock()

    with patch(
        "cnki_downloader.core.api_probe.ensure_api_endpoints",
        new_callable=AsyncMock,
    ), patch(
        "cnki_downloader.core.search._browser_search",
        side_effect=RuntimeError("连接超时"),
    ):
        with pytest.raises(SearchError, match="连接超时"):
            await search(session, SearchQuery(keyword="test"))
