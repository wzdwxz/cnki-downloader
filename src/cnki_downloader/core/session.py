"""httpx客户端封装 — User-Agent轮换、请求延时、Cookie维护"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

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
CNKI_SEARCH_URL = "https://kns.cnki.net/kns2/request/SearchHandler.ashx"
CNKI_SEARCH_RESULT_URL = "https://kns.cnki.net/kns2/brief/brief.aspx"
CNKI_DETAIL_URL = "https://kns.cnki.net/kcms2/article/abstract"


class SessionManager:
    """管理httpx异步客户端，统一处理请求头、延时、Cookie。"""

    def __init__(
        self,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        timeout: float = 30.0,
    ) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True,
                headers=self._build_headers(),
            )
        return self._client

    def _build_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": CNKI_BASE_URL,
        }

    async def _random_delay(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        client = await self._ensure_client()
        await self._random_delay()
        client.headers["User-Agent"] = random.choice(_USER_AGENTS)
        return await client.get(url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        client = await self._ensure_client()
        await self._random_delay()
        client.headers["User-Agent"] = random.choice(_USER_AGENTS)
        return await client.post(url, **kwargs)

    async def stream_download(
        self, url: str, **kwargs: Any
    ) -> httpx.Response:
        """返回流式响应，调用方需自行处理async iteration。"""
        client = await self._ensure_client()
        await self._random_delay()
        client.headers["User-Agent"] = random.choice(_USER_AGENTS)
        return await client.send(
            client.build_request("GET", url, **kwargs),
            stream=True,
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> SessionManager:
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
