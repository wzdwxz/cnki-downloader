"""cnki convert <file.caj> — CAJ转PDF命令"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cnki_downloader.core.converter import convert_caj_to_pdf

console = Console()


def convert_command(
    caj_file: Path = typer.Argument(..., help="CAJ文件路径", exists=True),
    output: Path = typer.Option(None, "--output", "-o", help="输出PDF路径"),
    delete: bool = typer.Option(False, "--delete", "-d", help="转换后删除原CAJ文件"),
) -> None:
    """将CAJ文件转换为PDF格式。"""
    try:
        with console.status(f"正在转换 [bold]{caj_file.name}[/bold] ..."):
            pdf_path = convert_caj_to_pdf(caj_file, output, delete_caj=delete)

        console.print(f"[green]转换完成: {pdf_path}[/green]")

    except Exception as e:
        console.print(f"[red]转换失败: {e}[/red]")
        raise typer.Exit(1)
