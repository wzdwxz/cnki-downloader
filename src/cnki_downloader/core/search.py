"""搜索引擎：通过 Playwright 浏览器自动化搜索知网 kns8s，支持高级搜索

知网已将搜索接口从 kns2 迁移至 kns8s，并强制要求浏览器级验证（滑块验证码），
纯 HTTP 请求无法绕过。因此搜索采用 Playwright 驱动真实浏览器完成。
"""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import quote

from cnki_downloader.core.api_probe import get_current_endpoints
from cnki_downloader.core.exceptions import (
    CaptchaRequiredError,
    NoResultsError,
    SearchError,
)
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult
from cnki_downloader.utils.browser_auth import build_browser_context_kwargs, get_browser_state_file

logger = logging.getLogger(__name__)

# 文献类型 → kns8s URL 的 bCKY3 数据库代码
SOURCE_TYPE_CODES: dict[str, str] = {
    "期刊": "CJFQ",
    "博士": "CDFD",
    "硕士": "CMFD",
    "学位论文": "CDFD,CMFD",
    "会议": "CPFD",
    "报纸": "CCND",
    "图书": "CRLD",
    "年鉴": "CYFD",
    "标准": "SCSF",
    "专利": "SCOD",
    "成果": "SNAD",
    "学术辑刊": "CCJD",
}


async def search(
    session: SessionManager,
    query: SearchQuery,
) -> SearchResult:
    """执行知网搜索，返回解析后的搜索结果。

    使用 Playwright 浏览器自动化搜索 kns8s 接口。
    session 参数保留以维持接口兼容，浏览器 Cookie 从 session 的持久化状态加载。
    首次搜索时自动探测 API 端点版本。
    """
    from cnki_downloader.core.api_probe import ensure_api_endpoints

    try:
        # 首次搜索时确保 API 端点信息可用（探测 + 缓存）
        await ensure_api_endpoints()
        return await _browser_search(query)
    except (NoResultsError, CaptchaRequiredError):
        raise
    except Exception as e:
        raise SearchError(f"搜索失败: {e}") from e


def _build_search_url(query: SearchQuery) -> str:
    """构造 kns8s 搜索 URL，使用自动探测的 API 端点。"""
    endpoints = get_current_endpoints()
    search_url = endpoints.get(
        "search_url", "https://kns.cnki.net/kns8s/defaultresult/index"
    )

    # 拼接所有关键词（主关键词 + 额外关键词），空格表示 AND
    all_keywords = [query.keyword] + list(query.extra_keywords)
    combined = " ".join(kw for kw in all_keywords if kw)

    url = f"{search_url}?kw={quote(combined)}&korder=SU"

    # 日期过滤（提取年份）
    if query.start_date:
        year_match = re.search(r"(\d{4})", query.start_date)
        if year_match:
            url += f"&date_from={year_match.group(1)}"
    if query.end_date:
        year_match = re.search(r"(\d{4})", query.end_date)
        if year_match:
            url += f"&date_to={year_match.group(1)}"

    # 文献类型过滤
    if query.source_types:
        # source_types 可能已经是逗号分隔的代码（如 "CJFQ,CDFD"），也可能是中文名
        codes = []
        for part in query.source_types.split(","):
            part = part.strip()
            if part in SOURCE_TYPE_CODES:
                codes.append(SOURCE_TYPE_CODES[part])
            elif part.isalpha() and part.isupper():
                codes.append(part)  # 已经是代码
        if codes:
            url += f"&bCKY3={','.join(codes)}"

    # 作者过滤
    if query.author:
        url += f"&au={quote(query.author)}"

    # 期刊过滤
    if query.journal:
        url += f"&base={quote(query.journal)}"

    return url


async def _browser_search(query: SearchQuery) -> SearchResult:
    """通过 Playwright 执行浏览器搜索。

    流程：headless 搜索 → 遇到验证码自动弹出 headed 浏览器 →
    用户完成验证后保存 Cookie → 用 headless 重试搜索。
    """
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as e:
        if e.name and e.name.startswith("playwright"):
            raise SearchError(
                "搜索需要 Playwright，请运行：\n"
                "pip install playwright && python -m playwright install chromium",
                user_hint="请安装 Playwright 后重试搜索",
            ) from e
        raise SearchError(f"搜索启动失败: {e}") from e

    search_url = _build_search_url(query)
    logger.debug("搜索URL: %s", search_url)

    # 最多尝试 2 次：第 1 次 headless，遇验证码后 headed 验证再 headless 重试
    for attempt in range(2):
        state_file = get_browser_state_file()
        ctx_kwargs = build_browser_context_kwargs()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()

            try:
                await page.goto(search_url, timeout=30000)

                # 检测验证码
                if "verify" in page.url:
                    await browser.close()
                    if attempt == 0:
                        logger.info("检测到验证码，切换为有界面模式进行验证...")
                        await _headed_captcha_verify(pw, search_url)
                        continue  # 验证完成后重试
                    else:
                        raise CaptchaRequiredError(
                            "验证码验证后仍需验证，请稍后重试"
                        )

                # 等待结果表格加载
                try:
                    await page.wait_for_selector(
                        "table.result-table-list tbody tr", timeout=15000
                    )
                except Exception:
                    await asyncio.sleep(2)

                # 再次检查验证码（可能延迟触发）
                if "verify" in page.url:
                    await browser.close()
                    if attempt == 0:
                        logger.info("延迟触发验证码，切换为有界面模式...")
                        await _headed_captcha_verify(pw, search_url)
                        continue
                    else:
                        raise CaptchaRequiredError("验证码验证后仍需验证，请稍后重试")

                # 中外文语言过滤（通过点击页面按钮实现）
                if query.language:
                    await _apply_language_filter(page, query.language)

                # 翻页到指定页码
                if query.page > 1:
                    for target_page in range(2, query.page + 1):
                        try:
                            next_btn = page.locator(
                                f"a[data-page='{target_page}']"
                            ).first
                            if not await next_btn.is_visible(timeout=2000):
                                next_btn = page.locator(
                                    "a#PageNext, a.next"
                                ).first
                            await next_btn.click()
                            try:
                                await page.wait_for_load_state(
                                    "networkidle", timeout=8000
                                )
                            except Exception:
                                await asyncio.sleep(2)
                        except Exception:
                            break

                # 解析总数
                total_count = await _parse_total_count(page)

                # 解析结果
                papers = await _parse_search_results(page)

                if not papers:
                    raise NoResultsError(f"未找到关于 '{query.keyword}' 的结果")

                if not total_count:
                    total_count = len(papers)

                # 保存浏览器状态（Cookie 持久化）
                try:
                    state_file.parent.mkdir(parents=True, exist_ok=True)
                    await context.storage_state(path=str(state_file))
                except Exception:
                    pass

                return SearchResult(
                    query=query,
                    papers=papers,
                    total_count=total_count,
                    page=query.page,
                )
            finally:
                if browser.is_connected():
                    await browser.close()

    raise SearchError("搜索失败：多次尝试后仍无法完成")


async def _headed_captcha_verify(pw, trigger_url: str) -> None:
    """弹出有界面的浏览器，让用户手动完成验证码，然后保存 Cookie。"""
    state_file = get_browser_state_file()
    ctx_kwargs = build_browser_context_kwargs()

    logger.info("正在打开浏览器窗口，请完成验证码验证...")
    print("\n" + "=" * 60)
    print("  [!] 知网需要安全验证（滑块验证码）")
    print("  请在弹出的浏览器窗口中完成验证")
    print("  完成后会自动继续搜索...")
    print("=" * 60 + "\n")

    browser = await pw.chromium.launch(headless=False, slow_mo=100)
    context = await browser.new_context(**ctx_kwargs)
    page = await context.new_page()

    try:
        await page.goto(trigger_url, timeout=30000)

        # 等待用户完成验证（URL 不再包含 verify）
        if "verify" in page.url:
            try:
                await page.wait_for_url(
                    lambda url: "verify" not in url,
                    timeout=120000,  # 最多等 2 分钟
                )
                print("  [OK] 验证通过！\n")
            except Exception:
                raise CaptchaRequiredError(
                    "验证超时，请重新运行搜索",
                    user_hint="验证码超时（2分钟），请重试",
                )

        await asyncio.sleep(1)

        # 保存浏览器状态
        state_file.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(state_file))
        logger.info("浏览器 Cookie 已保存")
    finally:
        await browser.close()


# 语言过滤值 → kns8s 页面按钮的 data-val 属性
_LANGUAGE_MAP: dict[str, str] = {
    "zh": "Chinese",
    "cn": "Chinese",
    "中文": "Chinese",
    "chinese": "Chinese",
    "en": "Foreign",
    "外文": "Foreign",
    "foreign": "Foreign",
}


async def _apply_language_filter(page, language: str) -> None:
    """在结果页点击中文/外文筛选按钮。

    知网 kns8s 的中外文筛选无法通过 URL 参数控制，
    必须通过页面交互点击筛选按钮来触发。
    """
    data_val = _LANGUAGE_MAP.get(language.lower().strip())
    if not data_val:
        logger.warning("未知的语言过滤值: %s（可选: zh/中文, en/外文）", language)
        return

    try:
        btn = page.locator(f'a[data-val="{data_val}"]').first
        if await btn.is_visible(timeout=3000):
            logger.debug("点击语言筛选: %s (%s)", language, data_val)
            await btn.click()
            # 等待结果表格刷新
            await asyncio.sleep(1)
            try:
                await page.wait_for_selector(
                    "table.result-table-list tbody tr", timeout=10000
                )
            except Exception:
                await asyncio.sleep(2)
        else:
            logger.debug("未找到语言筛选按钮: %s", data_val)
    except Exception as e:
        logger.warning("语言筛选失败: %s", e)


async def _parse_total_count(page) -> int:
    """从结果页解析总结果数。"""
    try:
        count_el = page.locator(".pagerTitleCell em, .result-count").first
        if await count_el.is_visible(timeout=3000):
            count_text = await count_el.inner_text()
            m = re.search(r"([\d,]+)", count_text)
            if m:
                return int(m.group(1).replace(",", ""))
    except Exception:
        pass
    return 0


async def _parse_search_results(page) -> list[Paper]:
    """解析 kns8s 搜索结果页面。

    Returns:
        Paper 列表
    """
    papers: list[Paper] = []

    try:
        await page.wait_for_selector(
            "table.result-table-list tbody tr", timeout=8000
        )
    except Exception:
        return papers

    rows = page.locator("table.result-table-list tbody tr")
    count = await rows.count()

    for i in range(count):
        try:
            row = rows.nth(i)

            # 标题
            title_el = row.locator("td.name a.fz14").first
            if not await title_el.is_visible(timeout=1000):
                title_el = row.locator("td.name a").first
            title = (await title_el.inner_text()).strip()
            href = await title_el.get_attribute("href") or ""
            if href and not href.startswith("http"):
                href = "https://kns.cnki.net" + href

            # 作者
            try:
                author_el = row.locator("td.author").first
                author_text = (await author_el.inner_text()).strip()
                authors = [
                    a.strip()
                    for a in author_text.replace("；", ";").split(";")
                    if a.strip()
                ]
            except Exception:
                authors = []

            # 来源期刊（新版可能没有 <a> 标签，直接读 td 文本）
            journal = ""
            try:
                source_td = row.locator("td.source").first
                source_a = source_td.locator("a").first
                if await source_a.count() > 0 and await source_a.is_visible(timeout=500):
                    journal = (await source_a.inner_text()).strip()
                else:
                    journal = (await source_td.inner_text()).strip()
            except Exception:
                pass

            # 发表日期
            try:
                date_el = row.locator("td.date").first
                pub_date = (await date_el.inner_text()).strip()
            except Exception:
                pub_date = ""

            # 文献类型标签
            doc_type = ""
            try:
                dtype_el = row.locator("td.data").first
                doc_type = (await dtype_el.inner_text()).strip()
            except Exception:
                pass

            # 从 URL 提取 dbname / filename
            dbname = ""
            filename = ""
            if href:
                db_m = re.search(r"dbname=(\w+)", href, re.IGNORECASE)
                fn_m = re.search(r"filename=(\w+)", href, re.IGNORECASE)
                if db_m:
                    dbname = db_m.group(1)
                if fn_m:
                    filename = fn_m.group(1)

            if title:
                paper = Paper(
                    title=title,
                    authors=authors,
                    journal=journal,
                    publish_date=pub_date,
                    url=href,
                    dbname=dbname,
                    filename=filename,
                )
                paper.doc_type = doc_type
                papers.append(paper)
        except Exception:
            continue

    return papers
