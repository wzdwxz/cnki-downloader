"""Typer CLI 应用入口"""

from __future__ import annotations

import typer

from cnki_downloader.cli.commands import convert, download, search
from cnki_downloader.cli.commands.auth import auth_app
from cnki_downloader.cli.commands.library import library_app

app = typer.Typer(
    name="cnki",
    help="CNKI文献下载器 — 搜索、下载、转换知网文献",
    no_args_is_help=True,
)

app.command(name="search", help="搜索知网文献")(search.search_command)
app.command(name="download", help="下载知网文献")(download.download_command)
app.command(name="convert", help="CAJ转PDF")(convert.convert_command)
app.add_typer(auth_app, name="auth")
app.add_typer(library_app, name="library")


@app.command(name="gui", help="启动图形界面")
def gui_command(
    theme: str = typer.Option("light", "--theme", "-t", help="主题: light / dark"),
) -> None:
    """启动PyQt6图形界面。"""
    from cnki_downloader.gui.app import run_gui

    run_gui(theme=theme)


def main() -> None:
    app()
