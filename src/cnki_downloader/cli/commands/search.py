"""cnki search "关键词" — CLI搜索命令，支持高级搜索"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from cnki_downloader.cli.formatters import format_search_results
from cnki_downloader.core.search import search
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.search_result import SearchQuery

console = Console()


def search_command(
    keyword: str = typer.Argument(..., help="搜索关键词"),
    author: str = typer.Option("", "--author", "-a", help="作者"),
    journal: str = typer.Option("", "--journal", "-j", help="期刊"),
    start_date: str = typer.Option("", "--from", help="起始日期 (YYYY-MM-DD)"),
    end_date: str = typer.Option("", "--to", help="截止日期 (YYYY-MM-DD)"),
    page: int = typer.Option(1, "--page", "-p", help="页码"),
) -> None:
    """搜索知网文献。支持按作者、期刊、日期范围过滤。"""
    query = SearchQuery(
        keyword=keyword,
        author=author,
        journal=journal,
        start_date=start_date,
        end_date=end_date,
        page=page,
    )
    asyncio.run(_search_async(query))


async def _search_async(query: SearchQuery) -> None:
    async with SessionManager() as session:
        filter_desc = query.keyword
        if query.author:
            filter_desc += f" 作者:{query.author}"
        if query.journal:
            filter_desc += f" 期刊:{query.journal}"

        with console.status(f"正在搜索 [bold]{filter_desc}[/bold] ..."):
            result = await search(session, query)

        format_search_results(console, result)
