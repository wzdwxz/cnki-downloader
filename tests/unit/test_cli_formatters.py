"""CLI formatter tests."""

from __future__ import annotations

import io

from rich.console import Console

from cnki_downloader.cli.formatters import _sanitize_for_console, format_search_results
from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult


class FakeTextIO(io.StringIO):
    @property
    def encoding(self) -> str:
        return "gbk"


def test_sanitize_for_console_replaces_unencodable_chars() -> None:
    console = Console(file=FakeTextIO())

    assert _sanitize_for_console(console, "Victor Vadmand Jensen, Marianne Johanssonø") == (
        "Victor Vadmand Jensen, Marianne Johansson?"
    )


def test_format_search_results_sanitizes_table_cells_for_gbk_console() -> None:
    console = Console(file=FakeTextIO())

    result = SearchResult(
        query=SearchQuery(keyword="人工智能"),
        papers=[
            Paper(
                title="Tailored AI ethics: Enacting geriatric care with Johanssonø",
                authors=["Victor Vadmand Jensen", "Marianne Johanssonø"],
                journal="Social Science & Medicine",
                publish_date="2026-03-26",
                url="https://example.com",
            )
        ],
        total_count=1,
        page=1,
    )

    format_search_results(console, result)

    assert "Johansson?" in console.file.getvalue()
