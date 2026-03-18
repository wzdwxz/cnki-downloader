"""搜索后台线程 — 使用 Playwright 浏览器搜索知网 kns8s

通过 BrowserThread 复用持久化浏览器实例，使用智能等待替代固定延迟。
"""

from __future__ import annotations

import asyncio
import re

from PyQt6.QtCore import QThread, pyqtSignal

from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult

# 文献类型 → kns8s URL 的 bCKY3 代码
SOURCE_TYPE_CODES = {
    "期刊": "CJFQ",
    "博士": "CDFD",
    "硕士": "CMFD",
    "会议": "CPFD",
    "报纸": "CCND",
}


class SearchWorker(QThread):
    """后台搜索线程 — 通过 BrowserThread 复用浏览器。"""

    finished = pyqtSignal(SearchResult)
    error = pyqtSignal(str)

    def __init__(
        self,
        query: SearchQuery,
        browser_thread,
        source_types: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._query = query
        self._browser_thread = browser_thread
        self._source_types = source_types or []

    def run(self) -> None:
        try:
            future = self._browser_thread.submit(self._search())
            result = future.result(timeout=60)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    async def _search(self) -> SearchResult:
        """执行浏览器搜索，复用 BrowserThread 的持久化浏览器。"""
        query = self._query

        try:
            page = await self._browser_thread.get_page()
        except Exception:
            raise RuntimeError(
                "搜索需要 Playwright，请运行：\n"
                "pip install playwright && python -m playwright install chromium"
            )

        try:
            return await self._do_search(page, query)
        except Exception as e:
            # 浏览器可能崩溃，重置后重试一次
            if "Target closed" in str(e) or "Browser" in str(e):
                await self._browser_thread.reset_browser()
                page = await self._browser_thread.get_page()
                return await self._do_search(page, query)
            raise

    async def _do_search(self, page, query: SearchQuery) -> SearchResult:
        """在给定页面上执行搜索。"""
        from urllib.parse import quote

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

        # 智能等待：等结果表格出现，而非固定 sleep
        try:
            await page.wait_for_selector(
                "table.result-table-list tbody tr", timeout=10000
            )
        except Exception:
            # 可能无结果，继续尝试解析
            await asyncio.sleep(1)

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
                    # 智能等待：等待结果表格刷新
                    try:
                        await page.wait_for_load_state(
                            "networkidle", timeout=8000
                        )
                    except Exception:
                        await asyncio.sleep(1)
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
