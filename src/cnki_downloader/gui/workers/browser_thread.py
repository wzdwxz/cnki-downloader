"""持久化浏览器事件循环线程

提供一个专用的 asyncio 事件循环线程，浏览器在首次使用时启动，
之后所有搜索复用同一实例，应用退出时关闭。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
from pathlib import Path

from PyQt6.QtCore import QThread


def _get_cookie_file() -> Path:
    """获取 Cookie 文件路径。"""
    try:
        from cnki_downloader.utils.config import get_config_dir
        return get_config_dir() / "browser_state.json"
    except Exception:
        return Path.home() / ".cnki_downloader" / "browser_state.json"


class BrowserThread(QThread):
    """持久化 asyncio 事件循环线程，管理可复用的 Playwright 浏览器。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_ready = threading.Event()
        self._browser = None
        self._context = None
        self._page = None
        self._pw = None
        self._pw_context_manager = None

    def run(self) -> None:
        """启动事件循环（运行到 shutdown 被调用）。"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        self._loop.run_forever()
        # 事件循环停止后清理
        self._loop.run_until_complete(self._cleanup())
        self._loop.close()

    def submit(self, coro) -> concurrent.futures.Future:
        """从任意线程提交协程到事件循环，返回 Future。"""
        self._loop_ready.wait()
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def shutdown(self) -> None:
        """关闭浏览器和事件循环。"""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.wait(5000)

    async def get_page(self):
        """获取可复用的浏览器页面，首次调用时启动浏览器。"""
        if self._browser and self._browser.is_connected():
            return self._page

        from playwright.async_api import async_playwright

        self._pw_context_manager = async_playwright()
        self._pw = await self._pw_context_manager.__aenter__()
        self._browser = await self._pw.chromium.launch(headless=True)

        ctx_kwargs: dict = {
            "viewport": {"width": 1400, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        cookie_file = _get_cookie_file()
        if cookie_file.exists():
            try:
                data = json.loads(cookie_file.read_text(encoding="utf-8"))
                if data.get("cookies"):
                    ctx_kwargs["storage_state"] = str(cookie_file)
            except Exception:
                pass

        self._context = await self._browser.new_context(**ctx_kwargs)
        self._page = await self._context.new_page()
        return self._page

    async def reset_browser(self) -> None:
        """浏览器崩溃时重置，下次 get_page 会重新启动。"""
        await self._cleanup()

    async def _cleanup(self) -> None:
        """关闭浏览器和 Playwright。"""
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._pw_context_manager:
                await self._pw_context_manager.__aexit__(None, None, None)
        except Exception:
            pass
        self._browser = None
        self._context = None
        self._page = None
        self._pw = None
        self._pw_context_manager = None
