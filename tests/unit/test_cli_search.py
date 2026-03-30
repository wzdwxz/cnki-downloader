"""CLI search command tests."""

from __future__ import annotations

from contextlib import nullcontext

import pytest

from cnki_downloader.core.exceptions import CaptchaRequiredError
from cnki_downloader.models.search_result import SearchQuery, SearchResult


@pytest.mark.asyncio
async def test_search_async_opens_browser_auth_and_retries(monkeypatch) -> None:
    from cnki_downloader.cli.commands import search as search_mod

    result = SearchResult(query=SearchQuery(keyword="test"), papers=[], total_count=0, page=1)
    search_calls = {"count": 0}
    auth_calls = {"count": 0}
    format_calls = {"count": 0}

    class FakeSession:
        def __init__(self) -> None:
            self.close_calls = 0

        async def close(self) -> None:
            self.close_calls += 1

    fake_session = FakeSession()

    class FakeSessionManager:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, *exc):
            return None

    async def fake_search(session, query):
        search_calls["count"] += 1
        if search_calls["count"] == 1:
            raise CaptchaRequiredError("需要验证码")
        return result

    async def fake_complete_browser_verification() -> int:
        auth_calls["count"] += 1
        return 3

    monkeypatch.setattr(search_mod, "SessionManager", FakeSessionManager)
    monkeypatch.setattr(search_mod, "search", fake_search)
    monkeypatch.setattr(
        search_mod,
        "complete_browser_verification",
        fake_complete_browser_verification,
        raising=False,
    )
    monkeypatch.setattr(
        search_mod,
        "format_search_results",
        lambda console, r: format_calls.__setitem__("count", format_calls["count"] + 1),
    )
    monkeypatch.setattr(search_mod.console, "status", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(search_mod.console, "print", lambda *args, **kwargs: None)

    await search_mod._search_async(SearchQuery(keyword="test"))

    assert search_calls["count"] == 2
    assert auth_calls["count"] == 1
    assert fake_session.close_calls == 1
    assert format_calls["count"] == 1
