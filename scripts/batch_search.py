"""批量搜索知网文献并下载PDF — 自动化脚本"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from cnki_downloader.core.downloader import (
    ProgressCallback,
    batch_download,
)
from cnki_downloader.core.search import search
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.search_result import SearchQuery, SearchResult

console = Console()
logger = logging.getLogger(__name__)

# ── 搜索任务定义 ──────────────────────────────────────────────────

SEARCH_TASKS: list[dict] = [
    {
        "name": "组织公平+公务员",
        "query": SearchQuery(
            keyword="组织公平",
            extra_keywords=["公务员"],
            start_date="2020-01-01",
            end_date="2025-12-31",
        ),
    },
    {
        "name": "组织公正+公共部门+绩效",
        "query": SearchQuery(
            keyword="组织公正",
            extra_keywords=["公共部门", "绩效"],
            start_date="2020-01-01",
            end_date="2025-12-31",
        ),
    },
    {
        "name": "公平氛围+跨层次",
        "query": SearchQuery(
            keyword="公平氛围",
            extra_keywords=["跨层次"],
            start_date="2018-01-01",
            end_date="2025-12-31",
        ),
    },
    {
        "name": "领导成员交换差异化+公平",
        "query": SearchQuery(
            keyword="领导成员交换差异化",
            extra_keywords=["公平"],
            start_date="2018-01-01",
            end_date="2025-12-31",
        ),
    },
    {
        "name": "组织承诺+公务员+公平(仅期刊)",
        "query": SearchQuery(
            keyword="组织承诺",
            extra_keywords=["公务员", "公平"],
            start_date="2020-01-01",
            end_date="2025-12-31",
            source_types="CJFQ",  # 仅期刊
        ),
    },
]

# ── 输出目录 ──────────────────────────────────────────────────────

OUTPUT_BASE = Path.home() / "Downloads" / "cnki"


class RichProgress(ProgressCallback):
    """Rich进度条回调。"""

    def __init__(self, progress: Progress, task_map: dict[str, int]) -> None:
        self._progress = progress
        self._task_map = task_map

    def on_progress(self, task_id: str, downloaded: int, total: int) -> None:
        if task_id not in self._task_map:
            desc = task_id[:50] if len(task_id) > 50 else task_id
            self._task_map[task_id] = self._progress.add_task(
                desc, total=total or 0
            )
        rich_task = self._task_map[task_id]
        if total:
            self._progress.update(
                rich_task, completed=downloaded, total=total
            )

    def on_complete(self, task_id: str, file_path: Path) -> None:
        if task_id in self._task_map:
            self._progress.update(
                self._task_map[task_id], completed=100, total=100
            )

    def on_error(self, task_id: str, error: Exception) -> None:
        console.print(f"  [red]下载失败 [{task_id[:30]}]: {error}[/red]")


def display_results(name: str, result: SearchResult) -> None:
    """以表格形式展示搜索结果。"""
    table = Table(
        title=f"[bold]{name}[/bold]  (共 {result.total_count} 条)",
        show_lines=True,
    )
    table.add_column("#", width=4, justify="right")
    table.add_column("标题", max_width=60)
    table.add_column("作者", max_width=20)
    table.add_column("来源", max_width=15)
    table.add_column("日期", width=10)

    for i, p in enumerate(result.papers, 1):
        authors = ", ".join(p.authors[:3])
        if len(p.authors) > 3:
            authors += " 等"
        table.add_row(str(i), p.title, authors, p.journal, p.publish_date)

    console.print(table)
    console.print()


def save_results_json(
    all_results: list[tuple[str, SearchResult]], output_dir: Path
) -> Path:
    """将所有搜索结果保存为 JSON 汇总文件。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for name, result in all_results:
        papers_data = []
        for p in result.papers:
            papers_data.append({
                "title": p.title,
                "authors": p.authors,
                "journal": p.journal,
                "publish_date": p.publish_date,
                "doi": p.doi,
                "url": p.url,
                "dbname": p.dbname,
                "filename": p.filename,
            })
        summary.append({
            "search_name": name,
            "total_count": result.total_count,
            "papers_fetched": len(result.papers),
            "papers": papers_data,
        })

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"search_results_{ts}.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return json_path


async def run_all_searches(
    session: SessionManager,
) -> list[tuple[str, SearchResult]]:
    """依次执行所有搜索任务。"""
    all_results: list[tuple[str, SearchResult]] = []

    for i, task in enumerate(SEARCH_TASKS, 1):
        name = task["name"]
        query: SearchQuery = task["query"]

        console.rule(f"[bold cyan]搜索 {i}/{len(SEARCH_TASKS)}: {name}")

        try:
            with console.status(f"正在搜索 [bold]{name}[/bold] ..."):
                result = await search(session, query)

            display_results(name, result)
            all_results.append((name, result))

            # 翻页获取更多结果（最多取前3页）
            page = 2
            while result.has_more and page <= 3:
                with console.status(f"正在获取第 {page} 页 ..."):
                    query_next = SearchQuery(
                        keyword=query.keyword,
                        extra_keywords=query.extra_keywords,
                        author=query.author,
                        journal=query.journal,
                        start_date=query.start_date,
                        end_date=query.end_date,
                        page=page,
                        source_types=query.source_types,
                    )
                    next_result = await search(session, query_next)
                    result.papers.extend(next_result.papers)
                page += 1

            console.print(
                f"  [green]共获取 {len(result.papers)} 篇文献信息[/green]\n"
            )

        except Exception as e:
            console.print(f"  [red]搜索失败: {e}[/red]\n")

    return all_results


async def download_all(
    session: SessionManager,
    all_results: list[tuple[str, SearchResult]],
) -> dict[str, list[Path]]:
    """下载所有搜索到的文献 PDF。"""
    downloaded: dict[str, list[Path]] = {}

    for name, result in all_results:
        if not result.papers:
            continue

        output_dir = OUTPUT_BASE / name.replace("+", "_").replace("(", "").replace(")", "")
        output_dir.mkdir(parents=True, exist_ok=True)

        console.rule(f"[bold green]下载: {name} ({len(result.papers)} 篇)")

        progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
        )
        task_map: dict[str, int] = {}
        callback = RichProgress(progress, task_map)

        try:
            with progress:
                paths = await batch_download(
                    session,
                    result.papers,
                    output_dir,
                    callback,
                    max_concurrent=2,
                )
            downloaded[name] = paths
            console.print(
                f"  [green]下载完成: {len(paths)}/{len(result.papers)} 篇"
                f" -> {output_dir}[/green]\n"
            )
        except Exception as e:
            console.print(f"  [red]下载出错: {e}[/red]\n")
            downloaded[name] = []

    return downloaded


async def main() -> None:
    """主函数：搜索 → 展示 → 保存 → 下载。"""
    console.print()
    console.rule("[bold magenta]CNKI 批量文献搜索与下载")
    console.print()

    async with SessionManager(min_delay=2.0, max_delay=5.0) as session:
        # Phase 1: 搜索
        all_results = await run_all_searches(session)

        if not all_results:
            console.print("[red]所有搜索均失败，请检查网络连接。[/red]")
            return

        # Phase 2: 保存搜索结果为 JSON
        json_path = save_results_json(all_results, OUTPUT_BASE)
        console.print(f"\n[dim]搜索结果已保存: {json_path}[/dim]\n")

        # Phase 3: 汇总
        total_papers = sum(len(r.papers) for _, r in all_results)
        console.rule(f"[bold]搜索汇总: {len(all_results)} 个主题, 共 {total_papers} 篇")

        summary_table = Table(show_lines=True)
        summary_table.add_column("搜索主题", max_width=40)
        summary_table.add_column("知网总数", justify="right", width=10)
        summary_table.add_column("已获取", justify="right", width=8)
        for name, result in all_results:
            summary_table.add_row(
                name, str(result.total_count), str(len(result.papers))
            )
        console.print(summary_table)
        console.print()

        # Phase 4: 下载 PDF
        console.print(
            "[yellow]即将开始下载PDF，需要校园网或已登录的知网账号。[/yellow]"
        )
        console.print(
            "[yellow]按 Ctrl+C 可中断下载（搜索结果已保存到JSON）。[/yellow]\n"
        )

        try:
            downloaded = await download_all(session, all_results)
        except KeyboardInterrupt:
            console.print("\n[yellow]下载已中断[/yellow]")
            return

        # Phase 5: 最终汇总
        console.print()
        console.rule("[bold green]下载完成汇总")
        for name, paths in downloaded.items():
            console.print(f"  {name}: {len(paths)} 篇已下载")

        console.print(f"\n[bold]所有文件保存在: {OUTPUT_BASE}[/bold]")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main())
