"""httpx客户端封装 — User-Agent轮换、智能请求延时、Cookie维护、验证码检测"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx

from cnki_downloader.core.exceptions import CaptchaRequiredError
from cnki_downloader.utils.browser_auth import load_browser_state_cookies

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
]

CNKI_BASE_URL = "https://www.cnki.net"
CNKI_KNS8S_BASE = "https://kns.cnki.net/kns8s"
CNKI_SEARCH_URL = f"{CNKI_KNS8S_BASE}/defaultresult/index"
CNKI_ADV_SEARCH_URL = f"{CNKI_KNS8S_BASE}/AdvSearch"
CNKI_DETAIL_URL = "https://kns.cnki.net/kcms2/article/abstract"


class SessionManager:
    """管理httpx异步客户端，统一处理请求头、智能延时、Cookie。

    智能延时策略：仅在两次请求间隔不足 min_delay 时补齐延迟，
    而非每次请求前盲目等待 1-3 秒。大幅减少不必要的等待时间。
    """

    def __init__(
        self,
        min_delay: float = 0.5,
        max_delay: float = 1.5,
        timeout: float = 30.0,
    ) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout
        self._last_request_time: float = 0.0

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True,
                headers=self._build_headers(),
            )
            self._load_saved_browser_cookies(self._client)
        return self._client

    def _build_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": CNKI_BASE_URL,
        }

    def _load_saved_browser_cookies(self, client: httpx.AsyncClient) -> None:
        """Seed the HTTP client with persisted Playwright cookies when available."""
        for cookie in load_browser_state_cookies():
            name = cookie.get("name")
            value = cookie.get("value")
            if not name or value is None:
                continue

            kwargs: dict[str, str] = {}
            if cookie.get("domain"):
                kwargs["domain"] = cookie["domain"]
            if cookie.get("path"):
                kwargs["path"] = cookie["path"]

            client.cookies.set(name, value, **kwargs)

    async def _smart_delay(self) -> None:
        """智能延迟：仅在距上次请求间隔不足时补齐等待时间。"""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        target_delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < target_delay:
            await asyncio.sleep(target_delay - elapsed)
        self._last_request_time = time.monotonic()

    def _rotate_ua(self, client: httpx.AsyncClient) -> None:
        client.headers["User-Agent"] = random.choice(_USER_AGENTS)

    def _check_captcha(self, resp: httpx.Response) -> None:
        """检测响应是否被重定向到验证码页面。

        知网在请求过于频繁时会将请求重定向到包含 "verify" 的 URL，
        或在响应体中嵌入验证码相关内容。统一在此检测并抛出异常。
        """
        # 检查 URL 重定向到验证页
        if "verify" in str(resp.url):
            logger.warning("检测到知网验证码页面: %s", resp.url)
            raise CaptchaRequiredError(f"请求被重定向到验证页: {resp.url}")

        # 检查响应体中的验证码标记（仅对 HTML 响应检查）
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            # 只检查前 2000 字符，避免大页面性能问题
            text_head = resp.text[:2000] if hasattr(resp, "text") else ""
            if text_head and ("captcha" in text_head.lower() or "验证码" in text_head):
                logger.warning("检测到知网响应中包含验证码")
                raise CaptchaRequiredError("知网响应中包含验证码，请求可能过于频繁")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        client = await self._ensure_client()
        await self._smart_delay()
        self._rotate_ua(client)
        resp = await client.get(url, **kwargs)
        self._check_captcha(resp)
        return resp

    async def head(self, url: str, **kwargs: Any) -> httpx.Response:
        """发送 HEAD 请求，仅获取响应头，不下载响应体。"""
        client = await self._ensure_client()
        await self._smart_delay()
        self._rotate_ua(client)
        resp = await client.head(url, **kwargs)
        # HEAD 无响应体，仅检查 URL
        if "verify" in str(resp.url):
            raise CaptchaRequiredError(f"请求被重定向到验证页: {resp.url}")
        return resp

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        client = await self._ensure_client()
        await self._smart_delay()
        self._rotate_ua(client)
        resp = await client.post(url, **kwargs)
        self._check_captcha(resp)
        return resp

    async def stream_download(
        self, url: str, **kwargs: Any
    ) -> httpx.Response:
        """返回流式响应，调用方需自行处理async iteration。"""
        client = await self._ensure_client()
        await self._smart_delay()
        self._rotate_ua(client)
        resp = await client.send(
            client.build_request("GET", url, **kwargs),
            stream=True,
            follow_redirects=True,
        )
        # 流式下载只检查 URL（响应体尚未读取）
        if "verify" in str(resp.url):
            raise CaptchaRequiredError(f"下载被重定向到验证页: {resp.url}")
        return resp

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> SessionManager:
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
