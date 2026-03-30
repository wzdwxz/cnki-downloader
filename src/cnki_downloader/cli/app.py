"""Typer CLI app entrypoint."""

from __future__ import annotations

import typer

from cnki_downloader.cli.commands import convert, download, download_en, search
from cnki_downloader.cli.commands.auth import auth_app

app = typer.Typer(
    name="cnki",
    help="CNKI downloader CLI",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def default_callback(ctx: typer.Context) -> None:
    """Show help when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)


app.command(name="search", help="Search CNKI papers")(search.search_command)
app.command(name="download", help="Download CNKI papers")(download.download_command)
app.command(name="download-en", help="Download English OA papers")(download_en.download_en_command)
app.command(name="convert", help="Convert CAJ to PDF")(convert.convert_command)
app.add_typer(auth_app, name="auth")


@app.command(name="gui", help="Launch GUI")
def gui_command(
    theme: str = typer.Option("light", "--theme", "-t", help="Theme: light / dark"),
) -> None:
    """Launch PyQt6 GUI."""
    from cnki_downloader.gui.app import run_gui

    run_gui(theme=theme)


def main() -> None:
    app()
