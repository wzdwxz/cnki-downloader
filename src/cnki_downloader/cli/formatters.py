"""Rich终端输出格式化"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from cnki_downloader.models.search_result import SearchResult


def format_search_results(console: Console, result: SearchResult) -> None:
    """在终端以表格形式展示搜索结果。"""
    table = Table(
        title=f"搜索结果: {result.query.keyword} (共 {result.total_count} 条)",
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
            paper.title,
            authors,
            paper.journal,
            paper.publish_date,
        )

    console.print(table)

    if result.has_more:
        console.print(
            f"\n[dim]第 {result.page} 页 / "
            f"使用 --page 查看更多结果[/dim]"
        )
