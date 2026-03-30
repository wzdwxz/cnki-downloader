"""CLI download command tests."""

from __future__ import annotations

import io
from contextlib import nullcontext

import pytest
from rich.console import Console

from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult


class FakeTextIO(io.StringIO):
    @property
    def encoding(self) -> str:
        return "gbk"


@pytest.mark.asyncio
async def test_download_async_sanitizes_non_gbk_characters(monkeypatch, tmp_path) -> None:
    from cnki_downloader.cli.commands import download as download_mod

    test_console = Console(file=FakeTextIO())

    class FakeSessionManager:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *exc):
            return None

    async def fake_search(session, query: SearchQuery):
        return SearchResult(
            query=query,
            papers=[
                Paper(
                    title="Tailored AI ethics with Johanssonø",
                    authors=["Victor Vadmand Jensen", "Marianne Johanssonø"],
                    journal="Social Science & Medicine",
                    publish_date="2026-03-26",
                    url="https://example.com",
                )
            ],
            total_count=1,
            page=1,
        )

    monkeypatch.setattr(download_mod, "console", test_console)
    monkeypatch.setattr(download_mod, "SessionManager", FakeSessionManager)
    monkeypatch.setattr(download_mod, "search", fake_search)
    monkeypatch.setattr(test_console, "status", lambda *args, **kwargs: nullcontext())

    await download_mod._download_async("人工智能", tmp_path, 999, False, 1)

    assert "Johansson?" in test_console.file.getvalue()
