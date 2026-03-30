"""Browser auth helper tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cnki_downloader.core.exceptions import AuthError
from cnki_downloader.utils import browser_auth as browser_auth_mod


def test_load_browser_state_cookies_returns_empty_on_permission_error(
    monkeypatch, tmp_path
) -> None:
    state_file = tmp_path / "browser_state.json"

    monkeypatch.setattr(
        "cnki_downloader.utils.config.get_config_dir",
        lambda: tmp_path,
    )

    original_stat = Path.stat

    def fake_stat(self: Path, *args, **kwargs):
        if self == state_file:
            raise PermissionError("access denied")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)

    assert browser_auth_mod.load_browser_state_cookies() == []


@pytest.mark.asyncio
async def test_complete_browser_verification_raises_on_timeout(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        browser_auth_mod,
        "get_browser_state_file",
        lambda: tmp_path / "browser_state.json",
    )

    class FakePage:
        async def goto(self, url: str, timeout: int) -> None:
            return None

        async def wait_for_event(self, event: str, timeout: int) -> None:
            raise TimeoutError("timed out")

    class FakeContext:
        async def new_page(self) -> FakePage:
            return FakePage()

        async def storage_state(self, path: str):
            return {"cookies": []}

    class FakeBrowser:
        async def new_context(self, **kwargs) -> FakeContext:
            return FakeContext()

        async def close(self) -> None:
            return None

    class FakeChromium:
        async def launch(self, headless: bool, slow_mo: int) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightManager:
        async def __aenter__(self) -> FakePlaywright:
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr("playwright.async_api.async_playwright", lambda: FakePlaywrightManager())

    with pytest.raises(AuthError, match="超时"):
        await browser_auth_mod.complete_browser_verification(timeout_ms=10)


@pytest.mark.asyncio
async def test_complete_browser_verification_raises_without_cnki_cookies(
    monkeypatch, tmp_path
) -> None:
    state_file = tmp_path / "browser_state.json"
    monkeypatch.setattr(browser_auth_mod, "get_browser_state_file", lambda: state_file)

    class FakePage:
        async def goto(self, url: str, timeout: int) -> None:
            return None

        async def wait_for_event(self, event: str, timeout: int) -> None:
            return None

    class FakeContext:
        async def new_page(self) -> FakePage:
            return FakePage()

        async def storage_state(self, path: str):
            Path(path).write_text('{"cookies": []}', encoding="utf-8")
            return {"cookies": []}

    class FakeBrowser:
        async def new_context(self, **kwargs) -> FakeContext:
            return FakeContext()

        async def close(self) -> None:
            return None

    class FakeChromium:
        async def launch(self, headless: bool, slow_mo: int) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightManager:
        async def __aenter__(self) -> FakePlaywright:
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr("playwright.async_api.async_playwright", lambda: FakePlaywrightManager())

    with pytest.raises(AuthError, match="Cookie"):
        await browser_auth_mod.complete_browser_verification()
