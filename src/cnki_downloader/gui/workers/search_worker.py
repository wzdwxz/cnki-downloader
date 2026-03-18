"""搜索后台线程 — 使用 Playwright 浏览器搜索知网 kns8s

每次搜索创建独立的浏览器实例，搜索结束后立即关闭。
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult


def _get_cookie_file() -> Path:
    """获取 Cookie 文件路径。"""
    try:
        from cnki_downloader.utils.config import get_config_dir
        return get_config_dir() / "browser_state.json"
    except Exception:
        return Path.home() / ".cnki_downloader" / "browser_state.json"


# 文献类型 → kns8s URL 的 bCKY3 代码
SOURCE_TYPE_CODES = {
    "期刊": "CJFQ",
    "博士": "CDFD",
    "硕士": "CMFD",
    "会议": "CPFD",
    "报纸": "CCND",
}


class SearchWorker(QThread):
    """后台搜索线程 — 每次搜索创建独立 Playwright 浏览器实例。"""

    finished = pyqtSignal(SearchResult)
    error = pyqtSignal(str)

    def __init__(
        self,
        query: SearchQuery,
        source_types: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._query = query
        self._source_types = source_types or []

    def run(self) -> None:
        try:
            result = asyncio.run(self._search())
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    async def _search(self) -> SearchResult:
        """执行浏览器搜索，每次创建独立的浏览器实例。"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "搜索需要 Playwright，请运行：\n"
                "pip install playwright && python -m playwright install chromium"
            )

        from urllib.parse import quote

        query = self._query
        cookie_file = _get_cookie_file()

        ctx_kwargs: dict = {
            "viewport": {"width": 1400, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        if cookie_file.exists():
            try:
                data = json.loads(cookie_file.read_text(encoding="utf-8"))
                if data.get("cookies"):
                    ctx_kwargs["storage_state"] = str(cookie_file)
            except Exception:
                pass

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(**ctx_kwargs)
                page = await context.new_page()

                # 构造搜索 URL
                search_url = (
                    f"https://kns.cnki.net/kns8s/defaultresult/index"
                    f"?kw={quote(query.keyword)}&korder=SU"
                )
                if query.start_date:
                    year_match = re.search(r"(\d{4})", query.start_date)
                    if year_match:
                        search_url += f"&date_from={year_match.group(1)}"
                if query.end_date:
                    year_match = re.search(r"(\d{4})", query.end_date)
                    if year_match:
                        search_url += f"&date_to={year_match.group(1)}"

                # 文献类型过滤
                if self._source_types:
                    codes = [
                        SOURCE_TYPE_CODES[t]
                        for t in self._source_types
                        if t in SOURCE_TYPE_CODES
                    ]
                    if codes:
                        search_url += f"&bCKY3={','.join(codes)}"

                await page.goto(search_url, timeout=30000)
                await asyncio.sleep(3)

                # 检查验证码
                if "verify" in page.url:
                    raise RuntimeError(
                        "知网需要验证，请先通过侧边栏「机构登录」完成认证"
                    )

                # 分页：翻到请求的页码
                if query.page > 1:
                    for target_page in range(2, query.page + 1):
                        try:
                            next_btn = page.locator(
                                f"a[data-page='{target_page}']"
                            ).first
                            if not await next_btn.is_visible(timeout=2000):
                                next_btn = page.locator("a#PageNext, a.next").first
                            await next_btn.click()
                            await asyncio.sleep(3)
                        except Exception:
                            break

                # 解析总数
                total_count = 0
                try:
                    count_el = page.locator(
                        ".pagerTitleCell em, .result-count"
                    ).first
                    if await count_el.is_visible(timeout=3000):
                        count_text = await count_el.inner_text()
                        m = re.search(r"([\d,]+)", count_text)
                        if m:
                            total_count = int(m.group(1).replace(",", ""))
                except Exception:
                    pass

                # 解析结果
                papers = await self._parse_results(page)

                # 按 doc_type 二次过滤
                if self._source_types:
                    papers = [
                        p for p in papers
                        if p.doc_type in self._source_types
                        or not p.doc_type
                    ]

                if not total_count:
                    total_count = len(papers)

                return SearchResult(
                    query=query,
                    papers=papers,
                    total_count=total_count,
                    page=query.page,
                )
            finally:
                await browser.close()

    async def _parse_results(self, page) -> list[Paper]:
        """解析 kns8s 结果页面。"""
        papers: list[Paper] = []

        # 等待结果表格
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

                # 来源
                try:
                    source_el = row.locator("td.source a").first
                    journal = (await source_el.inner_text()).strip()
                except Exception:
                    journal = ""

                # 日期
                try:
                    date_el = row.locator("td.date").first
                    pub_date = (await date_el.inner_text()).strip()
                except Exception:
                    pub_date = ""

                # 文献类型
                doc_type = ""
                try:
                    dtype_el = row.locator("td.data").first
                    doc_type = (await dtype_el.inner_text()).strip()
                except Exception:
                    pass

                # dbname / filename
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
