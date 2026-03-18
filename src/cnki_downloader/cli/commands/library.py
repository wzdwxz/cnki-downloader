"""cnki library — 文献库管理CLI命令"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cnki_downloader.core.export import (
    export_to_file,
)
from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import CategoryRepository, PaperRepository, TagRepository

console = Console()

library_app = typer.Typer(name="library", help="文献库管理", no_args_is_help=True)


@library_app.command(name="list")
def list_command(
    limit: int = typer.Option(20, "--limit", "-n", help="显示条数"),
    favorites: bool = typer.Option(False, "--favorites", "-f", help="仅显示收藏"),
    search: str = typer.Option("", "--search", "-s", help="搜索关键词"),
) -> None:
    """列出本地文献库中的文献。"""
    asyncio.run(_list_async(limit, favorites, search))


async def _list_async(limit: int, favorites: bool, search: str) -> None:
    async with Database() as db:
        repo = PaperRepository(db.conn)

        if search:
            papers = await repo.search_local(search)
        elif favorites:
            papers = await repo.list_favorites()
        else:
            papers = await repo.list_all(limit=limit)

        total = await repo.count()

    if not papers:
        console.print("[yellow]文献库为空[/yellow]")
        return

    table = Table(title=f"本地文献库 (共 {total} 篇)")
    table.add_column("ID", style="cyan", width=5)
    table.add_column("标题", style="bold", max_width=45)
    table.add_column("作者", max_width=20)
    table.add_column("期刊", style="green", max_width=15)
    table.add_column("收藏", width=4)
    table.add_column("本地文件", style="dim", max_width=30)

    for paper in papers:
        # We need the ID from database — use cnki_id as fallback display
        authors = ", ".join(paper.authors[:2])
        if len(paper.authors) > 2:
            authors += " 等"
        fav = "[red]★[/red]" if paper.is_favorite else ""
        local = paper.local_path.split("/")[-1] if paper.local_path else "--"
        table.add_row(
            paper.cnki_id[:5] or "--",
            paper.title,
            authors,
            paper.journal,
            fav,
            local,
        )

    console.print(table)


@library_app.command(name="export")
def export_command(
    output: Path = typer.Argument(..., help="输出文件路径"),
    fmt: str = typer.Option("bibtex", "--format", "-f", help="导出格式: bibtex, endnote, gbt7714"),
    search: str = typer.Option("", "--search", "-s", help="仅导出匹配的文献"),
) -> None:
    """导出文献引用。"""
    asyncio.run(_export_async(output, fmt, search))


async def _export_async(output: Path, fmt: str, search: str) -> None:
    async with Database() as db:
        repo = PaperRepository(db.conn)

        if search:
            papers = await repo.search_local(search)
        else:
            papers = await repo.list_all(limit=10000)

    if not papers:
        console.print("[yellow]没有可导出的文献[/yellow]")
        return

    try:
        path = export_to_file(papers, output, fmt)
        console.print(f"[green]已导出 {len(papers)} 篇文献到: {path}[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@library_app.command(name="tag")
def tag_command(
    action: str = typer.Argument(..., help="操作: create, list, delete"),
    name: str = typer.Option("", "--name", "-n", help="标签名称"),
    color: str = typer.Option("#808080", "--color", "-c", help="标签颜色"),
    tag_id: int = typer.Option(0, "--id", help="标签ID (用于删除)"),
) -> None:
    """管理标签。"""
    asyncio.run(_tag_async(action, name, color, tag_id))


async def _tag_async(action: str, name: str, color: str, tag_id: int) -> None:
    async with Database() as db:
        repo = TagRepository(db.conn)

        if action == "create":
            if not name:
                console.print("[red]请指定标签名称 --name[/red]")
                return
            tid = await repo.create(name, color)
            console.print(f"[green]标签已创建: {name} (ID: {tid})[/green]")

        elif action == "list":
            tags = await repo.list_all()
            if not tags:
                console.print("[yellow]暂无标签[/yellow]")
                return
            for t in tags:
                console.print(f"  [{t['color']}]●[/{t['color']}] {t['name']} (ID: {t['id']})")

        elif action == "delete":
            if not tag_id:
                console.print("[red]请指定标签ID --id[/red]")
                return
            await repo.delete(tag_id)
            console.print(f"[green]标签已删除 (ID: {tag_id})[/green]")

        else:
            console.print(f"[red]未知操作: {action}，可选: create, list, delete[/red]")


@library_app.command(name="category")
def category_command(
    action: str = typer.Argument(..., help="操作: create, list, delete"),
    name: str = typer.Option("", "--name", "-n", help="分类名称"),
    parent: int = typer.Option(0, "--parent", "-p", help="父分类ID"),
    cat_id: int = typer.Option(0, "--id", help="分类ID (用于删除)"),
) -> None:
    """管理分类目录。"""
    asyncio.run(_category_async(action, name, parent, cat_id))


async def _category_async(action: str, name: str, parent: int, cat_id: int) -> None:
    async with Database() as db:
        repo = CategoryRepository(db.conn)

        if action == "create":
            if not name:
                console.print("[red]请指定分类名称 --name[/red]")
                return
            parent_id = parent if parent else None
            cid = await repo.create(name, parent_id)
            console.print(f"[green]分类已创建: {name} (ID: {cid})[/green]")

        elif action == "list":
            cats = await repo.list_all()
            if not cats:
                console.print("[yellow]暂无分类[/yellow]")
                return
            for c in cats:
                indent = "  " if c["parent_id"] else ""
                prefix = "└─ " if c["parent_id"] else ""
                console.print(f"  {indent}{prefix}{c['name']} (ID: {c['id']})")

        elif action == "delete":
            if not cat_id:
                console.print("[red]请指定分类ID --id[/red]")
                return
            await repo.delete(cat_id)
            console.print(f"[green]分类已删除 (ID: {cat_id})[/green]")

        else:
            console.print(f"[red]未知操作: {action}，可选: create, list, delete[/red]")
