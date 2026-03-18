"""搜索查询和结果模型"""

from __future__ import annotations

from dataclasses import dataclass, field

from cnki_downloader.models.paper import Paper


@dataclass
class SearchQuery:
    """搜索查询参数"""

    keyword: str
    extra_keywords: list[str] = field(default_factory=list)
    author: str = ""
    journal: str = ""
    start_date: str = ""
    end_date: str = ""
    page: int = 1
    page_size: int = 20
    source_types: str = ""  # 数据库类型过滤，如 "CJFQ" 仅期刊


@dataclass
class SearchResult:
    """搜索结果"""

    query: SearchQuery
    papers: list[Paper] = field(default_factory=list)
    total_count: int = 0
    page: int = 1

    @property
    def has_more(self) -> bool:
        return self.page * self.query.page_size < self.total_count
