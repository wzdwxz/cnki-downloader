"""Download English papers from legal open-access sources."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from cnki_downloader.cli.formatters import _sanitize_for_console
from cnki_downloader.core.oa_downloader import (
    download_open_access_pdf,
    looks_like_doi,
    resolve_open_access_pdf,
)
from cnki_downloader.utils.config import load_config

console = Console()


def _safe(text: object) -> str:
    return _sanitize_for_console(console, str(text))


def download_en_command(
    query: str = typer.Argument(..., help="DOI or paper title"),
    output: Path = typer.Option(None, "--output", "-o", help="Output directory"),
    filename: str = typer.Option("", "--filename", help="Optional output filename"),
    email: str = typer.Option(
        "",
        "--email",
        help="Unpaywall contact email (or use CNKI_UNPAYWALL_EMAIL env var)",
    ),
) -> None:
    """Resolve and download English OA paper (PDF)."""
    config = load_config()
    output_dir = output or config.download_dir
    try:
        asyncio.run(
            _download_en_async(
                query=query,
                output_dir=output_dir,
                filename=filename,
                email=email,
            )
        )
    except Exception as exc:
        console.print(f"[red]English paper download failed:[/red] {_safe(exc)}")
        raise typer.Exit(code=1) from exc


async def _download_en_async(
    *,
    query: str,
    output_dir: Path,
    filename: str = "",
    email: str = "",
) -> Path:
    query = query.strip()
    doi = query if looks_like_doi(query) else ""
    title = "" if doi else query

    with console.status(f"Resolving OA source for: [bold]{_safe(query)}[/bold] ..."):
        result = await resolve_open_access_pdf(
            doi=doi,
            title=title,
            unpaywall_email=(email or None),
        )

    console.print(f"[green]Resolved provider:[/green] {_safe(result.provider)}")
    if result.doi:
        console.print(f"[dim]DOI:[/dim] {_safe(result.doi)}")

    with console.status("Downloading PDF ..."):
        path = await download_open_access_pdf(
            result=result,
            output_dir=output_dir,
            filename=filename,
        )

    console.print(f"[green]Download complete:[/green] {_safe(path)}")
    return path
