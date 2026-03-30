"""CNKI API 端点自动探测与版本检测

当知网升级搜索接口时（如 kns2 → kns8s），自动探测当前可用的 API 版本，
并更新 session 模块中的 URL 常量。探测结果缓存到本地配置文件，避免重复探测。
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 已知的 CNKI 搜索 API 版本，按优先级排列（最新在前）
_KNOWN_API_VERSIONS: list[dict[str, str]] = [
    {
        "version": "kns8s",
        "base": "https://kns.cnki.net/kns8s",
        "search_url": "https://kns.cnki.net/kns8s/defaultresult/index",
        "adv_search_url": "https://kns.cnki.net/kns8s/AdvSearch",
        "probe_url": "https://kns.cnki.net/kns8s/",
        "indicator": "kns8s",
    },
    {
        "version": "kns8",
        "base": "https://kns.cnki.net/kns8",
        "search_url": "https://kns.cnki.net/kns8/defaultresult/index",
        "adv_search_url": "https://kns.cnki.net/kns8/AdvSearch",
        "probe_url": "https://kns.cnki.net/kns8/",
        "indicator": "kns8",
    },
]

# 探测结果缓存有效期（秒）
_CACHE_TTL = 86400  # 24 小时


def _get_cache_file() -> Path:
    """返回 API 探测缓存文件路径。"""
    try:
        from cnki_downloader.utils.config import get_config_dir
        return get_config_dir() / "api_endpoints.json"
    except Exception:
        return Path.home() / ".cnki_downloader" / "api_endpoints.json"


def load_cached_endpoints() -> dict[str, Any] | None:
    """加载缓存的 API 端点信息。如果缓存过期或不存在则返回 None。"""
    cache_file = _get_cache_file()
    try:
        if not cache_file.exists():
            return None
    except OSError:
        return None

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    # 检查缓存是否过期
    cached_time = data.get("probe_time", 0)
    if time.time() - cached_time > _CACHE_TTL:
        logger.debug("API 端点缓存已过期")
        return None

    return data


def save_cached_endpoints(endpoints: dict[str, Any]) -> None:
    """保存 API 端点探测结果到缓存。"""
    cache_file = _get_cache_file()
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        endpoints["probe_time"] = time.time()
        cache_file.write_text(json.dumps(endpoints, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("API 端点信息已缓存: %s", endpoints.get("version"))
    except OSError as e:
        logger.warning("无法缓存 API 端点信息: %s", e)


async def probe_api_version() -> dict[str, str]:
    """探测当前可用的 CNKI 搜索 API 版本。

    优先使用缓存结果，缓存过期时重新探测。
    探测方式：依次访问已知版本的入口页面，检测响应中是否包含版本标识。

    Returns:
        包含 version, base, search_url, adv_search_url 的字典
    """
    # 先检查缓存
    cached = load_cached_endpoints()
    if cached and "version" in cached:
        logger.debug("使用缓存的 API 版本: %s", cached["version"])
        return cached

    logger.info("正在探测 CNKI API 版本...")

    async with httpx.AsyncClient(
        http2=True,
        timeout=15,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    ) as client:
        for api in _KNOWN_API_VERSIONS:
            try:
                resp = await client.get(api["probe_url"])
                final_url = str(resp.url)

                # 验证码页面也说明端点存在（只是需要验证）
                if "verify" in final_url:
                    logger.info("API 版本 %s 可用（需验证码）", api["version"])
                    result = {k: v for k, v in api.items() if k != "indicator"}
                    save_cached_endpoints(result)
                    return result

                # 检查响应内容中是否包含版本标识
                if resp.status_code == 200:
                    text_head = resp.text[:5000]
                    if api["indicator"] in text_head or api["indicator"] in final_url:
                        logger.info("API 版本 %s 可用", api["version"])
                        result = {k: v for k, v in api.items() if k != "indicator"}
                        save_cached_endpoints(result)
                        return result

            except Exception as e:
                logger.debug("探测 %s 失败: %s", api["version"], e)
                continue

    # 所有已知版本都不可用，回退到最新版本
    logger.warning("无法探测 API 版本，回退到默认 kns8s")
    fallback = {k: v for k, v in _KNOWN_API_VERSIONS[0].items() if k != "indicator"}
    return fallback


async def auto_detect_api_change() -> dict[str, str] | None:
    """检测 CNKI 是否升级了 API 版本。

    通过访问知网首页，解析 HTML 中的 APPPATH 变量来检测当前版本。
    如果发现新版本，自动更新缓存并返回新的端点信息。

    Returns:
        如果检测到版本变化，返回新的端点字典；否则返回 None
    """
    try:
        async with httpx.AsyncClient(
            http2=True, timeout=15, follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        ) as client:
            resp = await client.get("https://kns.cnki.net/")
            text = resp.text[:10000]

            # 解析 APPPATH 变量，如: var APPPATH = "\/kns8s";
            app_match = re.search(r'APPPATH\s*=\s*["\'].*?/(kns\w+)', text)
            if not app_match:
                return None

            detected_version = app_match.group(1)
            cached = load_cached_endpoints()
            current_version = cached.get("version", "") if cached else ""

            if detected_version != current_version:
                logger.info(
                    "检测到 CNKI API 版本变化: %s → %s",
                    current_version or "(未知)",
                    detected_version,
                )
                base = f"https://kns.cnki.net/{detected_version}"
                new_endpoints = {
                    "version": detected_version,
                    "base": base,
                    "search_url": f"{base}/defaultresult/index",
                    "adv_search_url": f"{base}/AdvSearch",
                }
                save_cached_endpoints(new_endpoints)
                return new_endpoints

    except Exception as e:
        logger.debug("API 版本检测失败: %s", e)

    return None


def get_current_endpoints() -> dict[str, str]:
    """同步获取当前 API 端点（优先从缓存读取）。

    用于不方便 await 的场景（如模块级常量初始化）。
    """
    cached = load_cached_endpoints()
    if cached and "search_url" in cached:
        return cached

    # 返回默认值
    return {
        "version": "kns8s",
        "base": "https://kns.cnki.net/kns8s",
        "search_url": "https://kns.cnki.net/kns8s/defaultresult/index",
        "adv_search_url": "https://kns.cnki.net/kns8s/AdvSearch",
    }


async def ensure_api_endpoints() -> dict[str, str]:
    """确保 API 端点信息可用（探测 + 缓存）。

    推荐在应用启动时调用一次。后续通过 get_current_endpoints() 同步获取。
    """
    cached = load_cached_endpoints()
    if cached and "search_url" in cached:
        return cached

    return await probe_api_version()
