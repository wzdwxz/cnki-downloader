"""cnki download - CLI download command with batch support."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TransferSpeedColumn,
)

from cnki_downloader.cli.formatters import _sanitize_for_console
from cnki_downloader.core.downloader import (
    ProgressCallback,
    batch_download,
    download_paper,
    paper_from_url,
)
from cnki_downloader.core.search import search
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery
from cnki_downloader.utils.config import load_config

console = Console()


def _safe_text(text: object) -> str:
    return _sanitize_for_console(console, str(text))


class RichProgress(ProgressCallback):
    """Progress callback implementation backed by Rich progress bars."""

    def __init__(self, progress: Progress, task_id_map: dict[str, int]) -> None:
        self._progress = progress
        self._task_map = task_id_map

    def on_progress(self, task_id: str, downloaded: int, total: int) -> None:
        if task_id not in self._task_map:
            self._task_map[task_id] = self._progress.add_task(
                _safe_text(task_id[:40]),
                total=total or 0,
            )
        rich_task = self._task_map[task_id]
        if total:
            self._progress.update(rich_task, completed=downloaded, total=total)

    def on_complete(self, task_id: str, file_path: Path) -> None:
        if task_id in self._task_map:
            self._progress.update(self._task_map[task_id], completed=100, total=100)

    def on_error(self, task_id: str, error: Exception) -> None:
        console.print(f"[red]下载失败 [{_safe_text(task_id[:30])}]: {_safe_text(error)}[/red]")


def download_command(
    query: str = typer.Argument(..., help="搜索关键词或文献URL"),
    output: Path = typer.Option(None, "--output", "-o", help="输出目录"),
    index: int = typer.Option(
        0, "--index", "-i", help="搜索结果中的序号（从1开始），0 表示交互选择"
    ),
    batch: bool = typer.Option(False, "--batch", "-b", help="批量下载所有搜索结果"),
    max_concurrent: int = typer.Option(3, "--concurrent", "-c", help="最大并发下载数"),
) -> None:
    """下载知网文献。支持单篇下载和批量下载。"""
    config = load_config()
    output_dir = output or config.download_dir
    asyncio.run(_download_async(query, output_dir, index, batch, max_concurrent))


async def _download_async(
    query: str, output_dir: Path, index: int, batch: bool, max_concurrent: int
) -> None:
    async with SessionManager() as session:
        if query.startswith("http"):
            paper = paper_from_url(query)
            await _download_single(session, paper, output_dir)
            return

        with console.status(f"正在搜索 [bold]{_safe_text(query)}[/bold] ..."):
            result = await search(session, SearchQuery(keyword=query))

        if not result.papers:
            console.print("[yellow]未找到相关文献[/yellow]")
            return

        for i, p in enumerate(result.papers, 1):
            console.print(f"  [cyan]{i:2d}[/cyan]. {_safe_text(p.short_info())}")

        if batch:
            console.print(f"\n[bold]批量下载 {len(result.papers)} 篇文献...[/bold]")
            await _download_batch(session, result.papers, output_dir, max_concurrent)
            return

        if index > 0:
            selected = index
        else:
            selected = int(
                typer.prompt("请输入要下载的文献序号（默认1）", default="1")
            )

        indices_str = str(selected)
        if "," in indices_str:
            indices = [int(x.strip()) for x in indices_str.split(",")]
            papers_to_download = []
            for idx in indices:
                if 1 <= idx <= len(result.papers):
                    papers_to_download.append(result.papers[idx - 1])
            if papers_to_download:
                await _download_batch(
                    session, papers_to_download, output_dir, max_concurrent
                )
            return

        selected = int(indices_str)
        if selected < 1 or selected > len(result.papers):
            console.print("[red]无效的序号[/red]")
            return

        await _download_single(session, result.papers[selected - 1], output_dir)


async def _download_single(
    session: SessionManager, paper: Paper, output_dir: Path
) -> None:
    console.print(f"\n正在下载: [bold]{_safe_text(paper.title)}[/bold]")

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
    )
    task_map: dict[str, int] = {}
    callback = RichProgress(progress, task_map)

    with progress:
        file_path = await download_paper(session, paper, output_dir, callback)

    console.print(f"\n[green]下载完成: {_safe_text(file_path)}[/green]")


async def _download_batch(
    session: SessionManager,
    papers: list[Paper],
    output_dir: Path,
    max_concurrent: int,
) -> None:
    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
    )
    task_map: dict[str, int] = {}
    callback = RichProgress(progress, task_map)

    with progress:
        paths = await batch_download(
            session, papers, output_dir, callback, max_concurrent=max_concurrent
        )

    console.print(f"\n[green]批量下载完成: {len(paths)} / {len(papers)} 篇[/green]")
    for p in paths:
        console.print(_safe_text(f"  {p}"))
