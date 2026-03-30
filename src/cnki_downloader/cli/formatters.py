"""Rich终端输出格式化"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from cnki_downloader.models.search_result import SearchResult


def _sanitize_for_console(console: Console, text: str) -> str:
    """Replace characters unsupported by the current console encoding."""
    encoding = getattr(getattr(console, "file", None), "encoding", None)
    if not encoding:
        return text

    try:
        text.encode(encoding)
        return text
    except UnicodeEncodeError:
        return text.encode(encoding, errors="replace").decode(encoding)


def format_search_results(console: Console, result: SearchResult) -> None:
    """在终端以表格形式展示搜索结果。"""
    table = Table(
        title=_sanitize_for_console(
            console, f"搜索结果: {result.query.keyword} (共 {result.total_count} 条)"
        ),
        show_lines=True,
    )
    table.add_column("#", style="cyan", width=4)
    table.add_column("标题", style="bold", max_width=50)
    table.add_column("作者", max_width=20)
    table.add_column("期刊", style="green", max_width=20)
    table.add_column("日期", style="dim", width=12)

    for i, paper in enumerate(result.papers, 1):
        authors = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors += " 等"
        table.add_row(
            str(i),
            _sanitize_for_console(console, paper.title),
            _sanitize_for_console(console, authors),
            _sanitize_for_console(console, paper.journal),
            _sanitize_for_console(console, paper.publish_date),
        )

    console.print(table)

    if result.has_more:
        console.print(
            _sanitize_for_console(
                console,
                f"\n[dim]第 {result.page} 页 / 使用 --page 查看更多结果[/dim]",
            )
        )
