"""引用导出：BibTeX / EndNote / GB/T 7714"""

from __future__ import annotations

import re
from pathlib import Path

from cnki_downloader.models.paper import Paper


def export_bibtex(papers: list[Paper]) -> str:
    """导出为BibTeX格式。"""
    entries: list[str] = []
    for paper in papers:
        key = _make_cite_key(paper)
        authors_str = " and ".join(paper.authors) if paper.authors else "Unknown"
        year = _extract_year(paper.publish_date)

        lines = [
            f"@article{{{key},",
            f"  title = {{{paper.title}}},",
            f"  author = {{{authors_str}}},",
        ]
        if paper.journal:
            lines.append(f"  journal = {{{paper.journal}}},")
        if year:
            lines.append(f"  year = {{{year}}},")
        if paper.doi:
            lines.append(f"  doi = {{{paper.doi}}},")
        if paper.keywords:
            lines.append(f"  keywords = {{{', '.join(paper.keywords)}}},")
        if paper.url:
            lines.append(f"  url = {{{paper.url}}},")
        lines.append("}")
        entries.append("\n".join(lines))

    return "\n\n".join(entries)


def export_endnote(papers: list[Paper]) -> str:
    """导出为EndNote标签格式 (.enw)。"""
    entries: list[str] = []
    for paper in papers:
        lines = [
            "%0 Journal Article",
            f"%T {paper.title}",
        ]
        for author in paper.authors:
            lines.append(f"%A {author}")
        if paper.journal:
            lines.append(f"%J {paper.journal}")
        year = _extract_year(paper.publish_date)
        if year:
            lines.append(f"%D {year}")
        if paper.doi:
            lines.append(f"%R {paper.doi}")
        if paper.keywords:
            for kw in paper.keywords:
                lines.append(f"%K {kw}")
        if paper.url:
            lines.append(f"%U {paper.url}")
        if paper.abstract:
            lines.append(f"%X {paper.abstract}")
        lines.append("")  # 空行分隔
        entries.append("\n".join(lines))

    return "\n".join(entries)


def export_gbt7714(papers: list[Paper]) -> str:
    """导出为GB/T 7714-2015参考文献格式。

    格式: [序号] 作者. 题名[J]. 刊名, 年, 卷(期): 页码.
    简化版（无卷期页码信息时省略）。
    """
    lines: list[str] = []
    for i, paper in enumerate(papers, 1):
        # 作者（前3位，超出用"等"）
        if paper.authors:
            if len(paper.authors) <= 3:
                authors_str = ", ".join(paper.authors)
            else:
                authors_str = ", ".join(paper.authors[:3]) + ", 等"
        else:
            authors_str = "佚名"

        year = _extract_year(paper.publish_date)

        parts = [f"[{i}] {authors_str}. {paper.title}[J]"]
        if paper.journal:
            parts.append(f". {paper.journal}")
        if year:
            parts.append(f", {year}")
        parts.append(".")

        if paper.doi:
            parts.append(f" DOI: {paper.doi}.")

        lines.append("".join(parts))

    return "\n".join(lines)


def export_to_file(
    papers: list[Paper],
    output_path: Path,
    fmt: str = "bibtex",
) -> Path:
    """导出引用到文件。

    Args:
        papers: 文献列表
        output_path: 输出文件路径
        fmt: 格式 — "bibtex", "endnote", "gbt7714"

    Returns:
        输出文件路径
    """
    exporters = {
        "bibtex": export_bibtex,
        "endnote": export_endnote,
        "gbt7714": export_gbt7714,
    }

    if fmt not in exporters:
        raise ValueError(f"不支持的导出格式: {fmt}，可选: {', '.join(exporters)}")

    content = exporters[fmt](papers)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _make_cite_key(paper: Paper) -> str:
    """生成BibTeX引用key。"""
    first_author = paper.authors[0] if paper.authors else "unknown"
    # 取姓氏拼音首字母或原文
    author_part = re.sub(r"[^a-zA-Z\u4e00-\u9fff]", "", first_author)[:10]
    year = _extract_year(paper.publish_date)
    # 取标题前两个词
    title_words = re.findall(r"[\w\u4e00-\u9fff]+", paper.title)[:2]
    title_part = "".join(title_words)[:15]
    return f"{author_part}{year}{title_part}"


def _extract_year(date_str: str) -> str:
    """从日期字符串中提取年份。"""
    match = re.search(r"(\d{4})", date_str)
    return match.group(1) if match else ""
