"""SessionManager persistence tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_session_manager_loads_saved_browser_cookies(monkeypatch) -> None:
    from cnki_downloader.core import session as session_mod

    monkeypatch.setattr(
        session_mod,
        "load_browser_state_cookies",
        lambda: [
            {
                "name": "SID",
                "value": "abc123",
                "domain": ".cnki.net",
                "path": "/",
            }
        ],
        raising=False,
    )

    manager = session_mod.SessionManager(min_delay=0, max_delay=0)

    client = await manager._ensure_client()

    assert client.cookies.get("SID", domain=".cnki.net", path="/") == "abc123"

    await manager.close()
