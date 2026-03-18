"""Paper, Author 数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Paper:
    """文献元数据"""

    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    journal: str = ""
    publish_date: str = ""
    doi: str = ""
    url: str = ""
    dbname: str = ""        # 知网数据库名，如 CJFDLAST
    filename: str = ""      # 知网文件名标识
    doc_type: str = "pdf"   # pdf / caj
    local_path: str = ""
    is_favorite: bool = False

    @property
    def cnki_id(self) -> str:
        """知网文献唯一标识: dbname + filename"""
        if self.dbname and self.filename:
            return f"{self.dbname}_{self.filename}"
        return ""

    def short_info(self) -> str:
        """简短信息，用于CLI展示。"""
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += " 等"
        parts = [self.title]
        if authors_str:
            parts.append(authors_str)
        if self.journal:
            parts.append(self.journal)
        if self.publish_date:
            parts.append(self.publish_date)
        return " | ".join(parts)
