"""cnki download — CLI下载命令，支持批量下载"""

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

from cnki_downloader.core.downloader import (
    ProgressCallback,
    batch_download,
    download_paper,
)
from cnki_downloader.core.search import search
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery
from cnki_downloader.utils.config import load_config

console = Console()


class RichProgress(ProgressCallback):
    """使用Rich进度条的回调实现。"""

    def __init__(self, progress: Progress, task_id_map: dict[str, int]) -> None:
        self._progress = progress
        self._task_map = task_id_map

    def on_progress(self, task_id: str, downloaded: int, total: int) -> None:
        if task_id not in self._task_map:
            self._task_map[task_id] = self._progress.add_task(
                task_id[:40], total=total or 0
            )
        rich_task = self._task_map[task_id]
        if total:
            self._progress.update(rich_task, completed=downloaded, total=total)

    def on_complete(self, task_id: str, file_path: Path) -> None:
        if task_id in self._task_map:
            self._progress.update(self._task_map[task_id], completed=100, total=100)

    def on_error(self, task_id: str, error: Exception) -> None:
        console.print(f"[red]下载失败 [{task_id[:30]}]: {error}[/red]")


def download_command(
    query: str = typer.Argument(..., help="搜索关键词或文献URL"),
    output: Path = typer.Option(None, "--output", "-o", help="输出目录"),
    index: int = typer.Option(
        0, "--index", "-i", help="搜索结果中的序号（从1开始），0表示交互选择"
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
        # 如果输入的是URL，直接下载
        if query.startswith("http"):
            paper = Paper(title="download", url=query)
            await _download_single(session, paper, output_dir)
            return

        # 搜索
        with console.status(f"正在搜索 [bold]{query}[/bold] ..."):
            search_query = SearchQuery(keyword=query)
            result = await search(session, search_query)

        if not result.papers:
            console.print("[yellow]未找到相关文献[/yellow]")
            return

        # 显示搜索结果
        for i, p in enumerate(result.papers, 1):
            console.print(f"  [cyan]{i:2d}[/cyan]. {p.short_info()}")

        # 批量下载
        if batch:
            console.print(f"\n[bold]批量下载 {len(result.papers)} 篇文献...[/bold]")
            await _download_batch(session, result.papers, output_dir, max_concurrent)
            return

        # 单篇选择下载
        if index > 0:
            selected = index
        else:
            selected = int(
                typer.prompt("\n请输入要下载的文献序号（多篇用逗号分隔，如1,3,5）", default="1")
            )

        # 支持逗号分隔的多选
        indices_str = str(selected)
        if "," in indices_str:
            indices = [int(x.strip()) for x in indices_str.split(",")]
            papers_to_download = []
            for idx in indices:
                if 1 <= idx <= len(result.papers):
                    papers_to_download.append(result.papers[idx - 1])
            if papers_to_download:
                await _download_batch(session, papers_to_download, output_dir, max_concurrent)
            return

        selected = int(indices_str)
        if selected < 1 or selected > len(result.papers):
            console.print("[red]无效的序号[/red]")
            return

        paper = result.papers[selected - 1]
        await _download_single(session, paper, output_dir)


async def _download_single(
    session: SessionManager, paper: Paper, output_dir: Path
) -> None:
    console.print(f"\n正在下载: [bold]{paper.title}[/bold]")

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

    console.print(f"\n[green]下载完成: {file_path}[/green]")


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
        console.print(f"  {p}")
