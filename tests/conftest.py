"""测试公共fixture"""

from __future__ import annotations

import pytest

from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult


@pytest.fixture
def sample_paper() -> Paper:
    return Paper(
        title="基于深度学习的文本分类方法研究",
        authors=["张三", "李四"],
        abstract="本文提出了一种新的文本分类方法...",
        keywords=["深度学习", "文本分类", "自然语言处理"],
        journal="计算机学报",
        publish_date="2024-01-15",
        url="https://kns.cnki.net/kcms2/article/abstract?v=abc123",
        dbname="CJFDLAST",
        filename="JSJX202401001",
    )


@pytest.fixture
def sample_query() -> SearchQuery:
    return SearchQuery(keyword="机器学习")


@pytest.fixture
def sample_search_result(sample_paper: Paper, sample_query: SearchQuery) -> SearchResult:
    return SearchResult(
        query=sample_query,
        papers=[sample_paper],
        total_count=100,
        page=1,
    )
