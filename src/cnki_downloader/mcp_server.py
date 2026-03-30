"""CNKI MCP Server — 知网文献搜索、下载、格式转换

通过 Model Context Protocol 暴露知网文献工具，
供 Claude Desktop / Claude Code 等 AI 客户端直接调用。

启动方式:
    python -m cnki_downloader.mcp_server
    # 或通过 entry point:
    cnki-mcp
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from cnki_downloader.core.exceptions import (
    CaptchaRequiredError,
    CnkiError,
    ConvertError,
    DownloadError,
    NoResultsError,
    SearchError,
)
from cnki_downloader.utils.config import load_config

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "cnki",
    instructions=(
        "知网(CNKI)文献工具。提供学术文献搜索、下载、CAJ→PDF格式转换功能。"
        "搜索前需确保已通过 cnki_auth_login 完成浏览器认证（保存Cookie）。"
    ),
)


# ── 辅助函数 ──────────────────────────────────────────────────────


def _paper_to_dict(paper) -> dict[str, Any]:
    """Paper dataclass → 可序列化的字典。"""
    d = dataclasses.asdict(paper)
    # 移除空值字段，让返回更简洁
    return {k: v for k, v in d.items() if v}


# ── 搜索工具 ──────────────────────────────────────────────────────


@mcp.tool()
async def cnki_search(
    keyword: str,
    extra_keywords: list[str] | None = None,
    author: str = "",
    journal: str = "",
    start_date: str = "",
    end_date: str = "",
    language: str = "",
    source_types: str = "",
    page: int = 1,
) -> dict[str, Any]:
    """搜索知网(CNKI)学术文献。

    Args:
        keyword: 搜索关键词（必填）
        extra_keywords: 额外关键词列表，与主关键词之间为 AND 关系
        author: 按作者过滤
        journal: 按期刊名过滤
        start_date: 起始日期，格式 YYYY 或 YYYY-MM-DD
        end_date: 截止日期，格式 YYYY 或 YYYY-MM-DD
        language: 语言过滤 — "zh"=仅中文, "en"=仅外文, ""=不限
        source_types: 文献类型过滤 — 如 "CJFQ"(期刊), "CDFD"(博士), "CMFD"(硕士),
                      也可用中文如 "期刊", "博士", "硕士", 多个用逗号分隔
        page: 页码，从1开始

    Returns:
        搜索结果，包含 total_count, page, papers 列表
    """
    from cnki_downloader.core.search import search
    from cnki_downloader.core.session import SessionManager
    from cnki_downloader.models.search_result import SearchQuery

    query = SearchQuery(
        keyword=keyword,
        extra_keywords=extra_keywords or [],
        author=author,
        journal=journal,
        start_date=start_date,
        end_date=end_date,
        language=language,
        source_types=source_types,
        page=page,
    )

    try:
        async with SessionManager() as session:
            result = await search(session, query)

        return {
            "total_count": result.total_count,
            "page": result.page,
            "has_more": result.has_more,
            "count": len(result.papers),
            "papers": [_paper_to_dict(p) for p in result.papers],
        }

    except CaptchaRequiredError as e:
        return {
            "error": "captcha_required",
            "message": str(e),
            "hint": "请先调用 cnki_auth_login 工具完成浏览器认证",
        }
    except NoResultsError:
        return {
            "total_count": 0,
            "page": page,
            "has_more": False,
            "count": 0,
            "papers": [],
            "message": f"未找到关于 '{keyword}' 的结果",
        }
    except SearchError as e:
        return {"error": "search_error", "message": str(e), "hint": e.user_hint}


# ── 下载工具 ──────────────────────────────────────────────────────


@mcp.tool()
async def cnki_download(
    url: str = "",
    keyword: str = "",
    index: int = 1,
    output_dir: str = "",
    batch: bool = False,
    max_concurrent: int = 3,
) -> dict[str, Any]:
    """下载知网文献 PDF。

    两种使用方式:
    1. 按 URL 下载: 提供文献详情页 URL
    2. 按关键词下载: 先搜索再下载指定序号的文献

    Args:
        url: 文献详情页 URL（与 keyword 二选一）
        keyword: 搜索关键词（与 url 二选一），先搜索再下载
        index: 搜索结果中的文献序号（从1开始），仅在 keyword 模式下有效
        output_dir: 下载目录，空则使用默认配置目录
        batch: 是否批量下载所有搜索结果（仅 keyword 模式）
        max_concurrent: 最大并发下载数

    Returns:
        下载结果，包含文件路径
    """
    from cnki_downloader.core.downloader import batch_download, download_paper
    from cnki_downloader.core.search import search
    from cnki_downloader.core.session import SessionManager
    from cnki_downloader.models.paper import Paper
    from cnki_downloader.models.search_result import SearchQuery

    if not url and not keyword:
        return {"error": "invalid_params", "message": "请提供 url 或 keyword 参数"}

    config = load_config()
    out_path = Path(output_dir) if output_dir else config.download_dir

    try:
        async with SessionManager() as session:
            if url:
                paper = Paper(title="download", url=url)
                file_path = await download_paper(session, paper, out_path)
                return {
                    "success": True,
                    "file_path": str(file_path),
                    "title": paper.title,
                }

            # keyword 模式: 先搜索
            query = SearchQuery(keyword=keyword)
            result = await search(session, query)

            if not result.papers:
                return {"error": "no_results", "message": f"未找到关于 '{keyword}' 的结果"}

            if batch:
                paths = await batch_download(
                    session, result.papers, out_path, max_concurrent=max_concurrent
                )
                return {
                    "success": True,
                    "downloaded": len(paths),
                    "total": len(result.papers),
                    "files": [str(p) for p in paths],
                }

            if index < 1 or index > len(result.papers):
                return {
                    "error": "invalid_index",
                    "message": f"序号 {index} 超出范围 (1-{len(result.papers)})",
                    "papers": [
                        {"index": i + 1, "title": p.title, "authors": p.authors}
                        for i, p in enumerate(result.papers[:10])
                    ],
                }

            paper = result.papers[index - 1]
            file_path = await download_paper(session, paper, out_path)
            return {
                "success": True,
                "file_path": str(file_path),
                "title": paper.title,
                "authors": paper.authors,
            }

    except CaptchaRequiredError as e:
        return {
            "error": "captcha_required",
            "message": str(e),
            "hint": "请先调用 cnki_auth_login 工具完成浏览器认证",
        }
    except DownloadError as e:
        return {"error": "download_error", "message": str(e), "hint": e.user_hint}
    except CnkiError as e:
        return {"error": "cnki_error", "message": str(e), "hint": e.user_hint}


# ── 格式转换工具 ──────────────────────────────────────────────────


@mcp.tool()
def cnki_convert(
    file_path: str,
    output_path: str = "",
    delete_original: bool = False,
) -> dict[str, Any]:
    """将 CAJ 格式文件转换为 PDF。

    Args:
        file_path: CAJ 文件路径
        output_path: 输出 PDF 路径，空则与原文件同名但扩展名为 .pdf
        delete_original: 转换成功后是否删除原 CAJ 文件

    Returns:
        转换结果，包含输出文件路径
    """
    from cnki_downloader.core.converter import convert_caj_to_pdf

    caj = Path(file_path)
    out = Path(output_path) if output_path else None

    try:
        pdf_path = convert_caj_to_pdf(caj, out, delete_caj=delete_original)
        return {
            "success": True,
            "output_path": str(pdf_path),
            "message": f"转换完成: {pdf_path.name}",
        }
    except ConvertError as e:
        return {"error": "convert_error", "message": str(e), "hint": e.user_hint}


# ── 认证工具 ──────────────────────────────────────────────────────


@mcp.tool()
def cnki_auth_status() -> dict[str, Any]:
    """检查知网认证状态（是否有已保存的浏览器 Cookie）。

    Returns:
        认证状态信息，包含 cookie 数量和状态文件路径
    """
    from cnki_downloader.utils.browser_auth import (
        get_browser_state_file,
        load_browser_state_cookies,
    )

    state_file = get_browser_state_file()
    cookies = load_browser_state_cookies()
    try:
        state_file_exists = state_file.exists()
    except OSError:
        state_file_exists = False

    # 提取关键 cookie 信息
    cnki_cookies = [c for c in cookies if "cnki" in c.get("domain", "")]

    return {
        "authenticated": len(cnki_cookies) > 0,
        "cookie_count": len(cookies),
        "cnki_cookie_count": len(cnki_cookies),
        "state_file": str(state_file),
        "state_file_exists": state_file_exists,
        "hint": (
            "已认证，Cookie 可用" if cnki_cookies
            else "未认证，请调用 cnki_auth_login 完成浏览器认证"
        ),
    }


@mcp.tool()
async def cnki_auth_login() -> dict[str, Any]:
    """打开浏览器完成知网认证（滑块验证码）。

    会弹出一个 Chromium 浏览器窗口，用户在其中完成验证后关闭窗口。
    认证后的 Cookie 会自动保存，后续搜索和下载可直接使用。

    Returns:
        认证结果，包含保存的 cookie 数量
    """
    from cnki_downloader.utils.browser_auth import complete_browser_verification

    try:
        cookie_count = await complete_browser_verification()
        return {
            "success": True,
            "cookie_count": cookie_count,
            "message": f"认证完成，已保存 {cookie_count} 条 Cookie",
        }
    except CnkiError as e:
        return {"error": "auth_error", "message": str(e), "hint": e.user_hint}
    except Exception as e:
        return {"error": "auth_error", "message": str(e)}


# ── 入口 ──────────────────────────────────────────────────────────


@mcp.tool()
async def cnki_download_en(
    doi: str = "",
    title: str = "",
    output_dir: str = "",
    filename: str = "",
    unpaywall_email: str = "",
) -> dict[str, Any]:
    """Download English paper from legal open-access sources."""
    from cnki_downloader.core.oa_downloader import (
        download_open_access_pdf,
        resolve_open_access_pdf,
    )

    if not doi and not title:
        return {
            "error": "invalid_params",
            "message": "Please provide doi or title",
        }

    config = load_config()
    out_path = Path(output_dir) if output_dir else config.download_dir

    try:
        result = await resolve_open_access_pdf(
            doi=doi,
            title=title,
            unpaywall_email=(unpaywall_email or None),
        )
        file_path = await download_open_access_pdf(
            result=result,
            output_dir=out_path,
            filename=filename,
        )
        return {
            "success": True,
            "provider": result.provider,
            "doi": result.doi,
            "title": result.title,
            "pdf_url": result.pdf_url,
            "file_path": str(file_path),
        }
    except DownloadError as e:
        return {"error": "download_error", "message": str(e), "hint": e.user_hint}
    except CnkiError as e:
        return {"error": "cnki_error", "message": str(e), "hint": e.user_hint}
    except Exception as e:
        return {"error": "download_error", "message": str(e)}


def main():
    """MCP Server 入口。"""
    mcp.run()


if __name__ == "__main__":
    main()
