"""Browser-based CNKI authentication helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cnki_downloader.core.exceptions import AuthError

CNKI_HOME_URL = "https://www.cnki.net"
_BROWSER_TIMEOUT_MS = 300_000


def get_browser_state_file() -> Path:
    """Return the persisted Playwright storage state path."""
    try:
        from cnki_downloader.utils.config import get_config_dir

        return get_config_dir() / "browser_state.json"
    except Exception:
        return Path.home() / ".cnki_downloader" / "browser_state.json"


def load_browser_state_cookies() -> list[dict[str, Any]]:
    """Load persisted browser cookies from storage state."""
    state_file = get_browser_state_file()
    try:
        if not state_file.exists():
            return []
    except OSError:
        return []

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []

    cookies = data.get("cookies", [])
    if not isinstance(cookies, list):
        return []
    return [cookie for cookie in cookies if isinstance(cookie, dict)]


def count_cnki_cookies(cookies: list[dict[str, Any]]) -> int:
    """Count cookies scoped to CNKI domains."""
    return sum(
        1
        for cookie in cookies
        if "cnki" in str(cookie.get("domain", "")).lower()
    )


def build_browser_context_kwargs() -> dict[str, Any]:
    """Build a shared Playwright browser context configuration."""
    kwargs: dict[str, Any] = {
        "viewport": {"width": 1400, "height": 900},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    state_file = get_browser_state_file()
    if load_browser_state_cookies():
        kwargs["storage_state"] = str(state_file)

    return kwargs


async def complete_browser_verification(timeout_ms: int = _BROWSER_TIMEOUT_MS) -> int:
    """Open a headed browser, let the user complete CNKI verification, and persist cookies."""
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as e:
        if e.name and e.name.startswith("playwright"):
            raise AuthError("验证码认证需要 Playwright，请安装后重试") from e
        raise AuthError(f"浏览器认证启动失败: {e}") from e
    except Exception as e:
        raise AuthError(f"浏览器认证启动失败: {e}") from e

    state_file = get_browser_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    ctx_kwargs = build_browser_context_kwargs()

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False, slow_mo=100)
            try:
                context = await browser.new_context(**ctx_kwargs)
                page = await context.new_page()
                await page.goto(CNKI_HOME_URL, timeout=30_000)

                try:
                    await page.wait_for_event("close", timeout=timeout_ms)
                except Exception as e:
                    raise AuthError(
                        "认证超时，请在浏览器中完成验证码或机构认证后关闭窗口再重试"
                    ) from e

                state = await context.storage_state(path=str(state_file))
                cookies = state.get("cookies", [])
                if not isinstance(cookies, list):
                    cookies = []
                cookie_count = len(cookies)
                if count_cnki_cookies(cookies) == 0:
                    raise AuthError("未检测到已保存的知网 Cookie，认证可能未完成")
                return cookie_count
            finally:
                await browser.close()
    except AuthError:
        raise
    except Exception as e:
        raise AuthError(f"浏览器认证失败: {e}") from e
