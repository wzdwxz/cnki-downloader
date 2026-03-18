"""搜索引擎：构造请求、解析搜索结果页，支持高级搜索"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from cnki_downloader.core.exceptions import NoResultsError, SearchError
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


async def search(
    session: SessionManager,
    query: SearchQuery,
) -> SearchResult:
    """执行知网搜索，返回解析后的搜索结果。支持高级搜索条件。"""
    try:
        # Step 1: 提交搜索请求，获取搜索cookie
        search_params = _build_search_params(query)
        resp = await session.post(
            "https://kns.cnki.net/kns2/request/SearchHandler.ashx",
            data=search_params,
        )
        resp.raise_for_status()

        # Step 2: 获取结果列表页
        result_params = {
            "pagename": resp.text.strip(),
            "t": "1",
            "keyValue": query.keyword,
            "S": "1",
            "sorttype": "",
        }
        if query.page > 1:
            result_params["curpage"] = str(query.page)

        result_resp = await session.get(
            "https://kns.cnki.net/kns2/brief/brief.aspx",
            params=result_params,
        )
        result_resp.raise_for_status()

        # Step 3: 解析结果页HTML
        papers, total_count = _parse_search_results(result_resp.text)

        if not papers:
            raise NoResultsError(f"未找到关于 '{query.keyword}' 的结果")

        return SearchResult(
            query=query,
            papers=papers,
            total_count=total_count,
            page=query.page,
        )

    except NoResultsError:
        raise
    except Exception as e:
        raise SearchError(f"搜索失败: {e}") from e


def _build_search_params(query: SearchQuery) -> dict[str, str]:
    """构造知网搜索表单参数，支持高级搜索条件。"""
    params: dict[str, str] = {
        "action": "",
        "NaviCode": "*",
        "ua": "1.21",
        "isinEn": "0",
        "PageName": "ASP.brief_result_aspx",
        "DbPrefix": "SCDB",
        "DbCatalog": "中国学术文献网络出版总库",
        "ConfigFile": "SCDB.xml",
        "db_opt": "CJFQ,CDFD,CMFD,CPFD,IPFD,CCND,CCJD",
        "his": "0",
        "parentdb": "SCDB",
        "CKY2Sty": "lstB",
        "__": "",
    }

    # 数据库类型过滤（如仅期刊 CJFQ）
    if query.source_types:
        params["db_opt"] = query.source_types

    # 主题/关键词搜索（第一个检索条件）
    params["txt_1_sel"] = "SU$%=|"
    params["txt_1_value1"] = query.keyword
    params["txt_1_special1"] = "%"

    # 高级搜索条件序号
    field_index = 2

    # 额外关键词条件（AND关系）
    for extra_kw in query.extra_keywords:
        params[f"txt_{field_index}_sel"] = "SU$%=|"
        params[f"txt_{field_index}_value1"] = extra_kw
        params[f"txt_{field_index}_special1"] = "%"
        params[f"txt_{field_index}_relation"] = "#DIFFAND"
        field_index += 1

    # 作者条件
    if query.author:
        params[f"txt_{field_index}_sel"] = "AU$%=|"
        params[f"txt_{field_index}_value1"] = query.author
        params[f"txt_{field_index}_special1"] = "%"
        params[f"txt_{field_index}_relation"] = "#DIFFAND"
        field_index += 1

    # 期刊条件
    if query.journal:
        params[f"txt_{field_index}_sel"] = "LY$%=|"
        params[f"txt_{field_index}_value1"] = query.journal
        params[f"txt_{field_index}_special1"] = "%"
        params[f"txt_{field_index}_relation"] = "#DIFFAND"
        field_index += 1

    # 日期范围
    if query.start_date:
        params["publishdate_from"] = query.start_date
    if query.end_date:
        params["publishdate_to"] = query.end_date

    return params


def _parse_search_results(html: str) -> tuple[list[Paper], int]:
    """解析知网搜索结果页面。

    Returns:
        (papers列表, 总结果数)
    """
    soup = BeautifulSoup(html, "lxml")
    papers: list[Paper] = []

    # 解析总数
    total_count = 0
    pager = soup.find("span", class_="pagerTitleCell")
    if pager:
        match = re.search(r"(\d[\d,]*)", pager.get_text())
        if match:
            total_count = int(match.group(1).replace(",", ""))

    # 解析结果表格
    table = soup.find("table", class_="GridTableContent")
    if not table:
        return [], total_count

    rows = table.find_all("tr")[1:]  # 跳过表头
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        try:
            # 标题列
            title_tag = cols[1].find("a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            detail_url = title_tag.get("href", "")
            if detail_url and not detail_url.startswith("http"):
                detail_url = "https://kns.cnki.net" + detail_url

            # 作者列
            authors = [
                a.get_text(strip=True)
                for a in cols[2].find_all("a")
            ]

            # 来源（期刊）列
            journal_tag = cols[3].find("a")
            journal = journal_tag.get_text(strip=True) if journal_tag else ""

            # 发表日期列
            publish_date = cols[4].get_text(strip=True)

            # 从URL中提取文献标识
            dbname = ""
            filename = ""
            if detail_url:
                db_match = re.search(r"dbname=(\w+)", detail_url, re.IGNORECASE)
                fn_match = re.search(r"filename=(\w+)", detail_url, re.IGNORECASE)
                if db_match:
                    dbname = db_match.group(1)
                if fn_match:
                    filename = fn_match.group(1)

            paper = Paper(
                title=title,
                authors=authors,
                journal=journal,
                publish_date=publish_date,
                url=detail_url,
                dbname=dbname,
                filename=filename,
            )
            papers.append(paper)

        except Exception as e:
            logger.warning("解析结果行失败: %s", e)
            continue

    return papers, total_count
