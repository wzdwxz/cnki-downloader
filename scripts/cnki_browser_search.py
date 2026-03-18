"""
CNKI 浏览器自动化搜索与下载脚本
使用 Playwright 控制真实浏览器，用户只需手动过一次验证码，
后续所有搜索和下载全自动完成。Cookie 会自动保存，下次运行无需重复验证。

用法:
  python scripts/cnki_browser_search.py                       # 使用默认设置
  python scripts/cnki_browser_search.py --output D:/papers    # 指定下载目录
  python scripts/cnki_browser_search.py --max 50              # 每个主题最多50篇
  python scripts/cnki_browser_search.py --max 30 -o D:/papers # 组合使用
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 修复 Windows 控制台编码，避免 GBK 无法输出 Unicode 字符
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace"
    )

# ── 搜索任务定义 ──────────────────────────────────────────────────


# ── 知网文献类型常量 ──────────────────────────────────────────────
# 直接使用中文名即可，脚本内部自动映射到 CNKI 数据库代码
# 可用值: "期刊", "博士", "硕士", "会议", "报纸", "图书", "年鉴",
#         "标准", "专利", "成果", "学术辑刊"
# 空列表 = 不限制（搜索全部类型）

SOURCE_TYPE_MAP: dict[str, str] = {
    "期刊": "CJFQ",
    "博士": "CDFD",
    "硕士": "CMFD",
    "学位论文": "CDFD,CMFD",  # 博士+硕士
    "会议": "CPFD",
    "报纸": "CCND",
    "图书": "CRLD",
    "年鉴": "CYFD",
    "标准": "SCSF",
    "专利": "SCOD",
    "成果": "SNAD",
    "学术辑刊": "CCJD",
}

# kns8s 页面上的文献类型勾选项名称（用于高级搜索表单操作）
PAGE_SOURCE_LABELS = [
    "学术期刊", "学位论文", "会议", "报纸", "图书",
    "年鉴", "标准", "专利", "成果", "学术辑刊",
]
# 页面标签 → db_opt 代码
PAGE_LABEL_TO_CODE: dict[str, str] = {
    "学术期刊": "CJFQ",
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


# dbname 前缀与文献类型的映射
DBNAME_PREFIX_MAP: dict[str, list[str]] = {
    "期刊": ["CJFQ", "CJFD"],
    "博士": ["CDFD"],
    "硕士": ["CMFD"],
    "学位论文": ["CDFD", "CMFD"],
    "会议": ["CPFD", "IPFD"],
    "报纸": ["CCND"],
    "图书": ["CRLD"],
    "年鉴": ["CYFD"],
    "标准": ["SCSF"],
    "专利": ["SCOD"],
    "成果": ["SNAD"],
    "学术辑刊": ["CCJD"],
}


# 用户指定类型 → 页面 td.data 列中对应的标签
SOURCE_TYPE_DOC_LABELS: dict[str, list[str]] = {
    "期刊": ["期刊"],
    "博士": ["博士"],
    "硕士": ["硕士"],
    "学位论文": ["博士", "硕士"],
    "会议": ["会议"],
    "报纸": ["报纸"],
    "图书": ["图书"],
    "年鉴": ["年鉴"],
    "标准": ["标准"],
    "专利": ["专利"],
    "成果": ["成果"],
    "学术辑刊": ["学术辑刊"],
}


def _get_allowed_doc_types(source_types: list[str]) -> list[str]:
    """根据用户指定的文献类型，返回允许的 doc_type 标签列表。"""
    if not source_types:
        return []
    labels: list[str] = []
    for st in source_types:
        for lb in SOURCE_TYPE_DOC_LABELS.get(st, [st]):
            if lb not in labels:
                labels.append(lb)
    return labels


def _filter_by_doc_type(
    papers: list[PaperInfo], allowed_types: list[str]
) -> list[PaperInfo]:
    """根据 doc_type 字段过滤文献，只保留目标类型。"""
    if not allowed_types:
        return papers
    return [
        p for p in papers
        if p.doc_type in allowed_types
        or not p.doc_type  # doc_type 为空时保留（无法判断）
    ]


def _resolve_source_codes(types: list[str]) -> str:
    """将用户友好的类型名列表转换为逗号分隔的 CNKI db_opt 代码。"""
    if not types:
        return ""
    codes: list[str] = []
    for t in types:
        mapped = SOURCE_TYPE_MAP.get(t, "")
        if mapped:
            for code in mapped.split(","):
                if code not in codes:
                    codes.append(code)
        else:
            print(f"  [WARN] 未知文献类型: {t}，可用: {', '.join(SOURCE_TYPE_MAP)}")
    return ",".join(codes)


@dataclass
class SearchTask:
    name: str
    keywords: list[str]
    start_year: int
    end_year: int
    source_types: list[str] = field(default_factory=list)
    # 中文名列表，如 ["期刊"] / ["期刊", "会议"] / [] 表示不限
    max_papers: int = 0  # 0 = 使用全局默认值


TASKS = [
    SearchTask(
        name="组织公平+公务员",
        keywords=["组织公平", "公务员"],
        start_year=2020,
        end_year=2025,
        source_types=["期刊"],
        max_papers=10,
    ),
]

def _parse_int_arg(*flags: str, default: int = 0) -> int:
    """从 sys.argv 解析整数参数。"""
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg in flags and i + 1 < len(sys.argv):
            try:
                return int(sys.argv[i + 1])
            except ValueError:
                pass
        for flag in flags:
            if arg.startswith(f"{flag}="):
                try:
                    return int(arg.split("=", 1)[1])
                except ValueError:
                    pass
    return default


def _get_output_dir() -> Path:
    """从命令行参数或配置文件获取下载目录。"""
    # 命令行参数: --output <路径>
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg in ("--output", "-o") and i < len(sys.argv):
            return Path(sys.argv[i + 1])
        if arg.startswith("--output="):
            return Path(arg.split("=", 1)[1])

    # 尝试从项目配置系统加载
    try:
        from cnki_downloader.utils.config import load_config
        return load_config().download_dir
    except Exception:
        pass

    # 最终回退
    return Path.home() / "Downloads" / "cnki"


def _get_cookie_dir() -> Path:
    """获取 Cookie 存储目录。"""
    try:
        from cnki_downloader.utils.config import get_config_dir
        return get_config_dir()
    except Exception:
        cookie_dir = Path.home() / ".cnki_downloader"
        cookie_dir.mkdir(parents=True, exist_ok=True)
        return cookie_dir


OUTPUT_DIR = _get_output_dir()
COOKIE_FILE = _get_cookie_dir() / "browser_state.json"
# 全局最大文献数，可用 --max N 覆盖，0 表示不限制
DEFAULT_MAX_PAPERS = _parse_int_arg("--max", "-m", default=0)


@dataclass
class PaperInfo:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    publish_date: str = ""
    url: str = ""
    download_url: str = ""
    dbname: str = ""
    filename: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    doc_type: str = ""  # 文献类型：期刊、硕士、博士、会议 等


async def wait_for_captcha(page) -> None:
    """等待用户完成验证码。如果检测到验证页面，提示用户手动操作。"""
    try:
        # 检查是否在验证页面
        if "verify" in page.url:
            print("\n" + "=" * 60)
            print("  [!] 检测到知网安全验证（滑块验证码）")
            print("  请在弹出的浏览器窗口中完成验证")
            print("  完成后脚本会自动继续...")
            print("=" * 60 + "\n")

            # 等待用户完成验证并跳转走
            await page.wait_for_url(
                lambda url: "verify" not in url,
                timeout=120000,  # 最多等2分钟
            )
            print("  [OK] 验证通过！\n")
            await asyncio.sleep(1)
    except Exception:
        pass


async def do_search(page, task: SearchTask) -> list[PaperInfo]:
    """在知网新版 kns8s 界面执行搜索。"""
    # 确定本次搜索的数量上限: 任务级 > 全局级, 0=不限
    limit = task.max_papers or DEFAULT_MAX_PAPERS

    print(f"\n{'─' * 50}")
    print(f"  搜索: {task.name}")
    print(f"  关键词: {' AND '.join(task.keywords)}")
    print(f"  年份: {task.start_year}-{task.end_year}")
    if task.source_types:
        print(f"  类型: {', '.join(task.source_types)}")
    if limit > 0:
        print(f"  数量上限: {limit} 篇")
    print(f"{'─' * 50}")

    # 导航到知网高级搜索
    await page.goto("https://kns.cnki.net/kns8s/AdvSearch", timeout=30000)
    await asyncio.sleep(2)

    # 检查验证码
    await wait_for_captcha(page)

    # 如果被重定向，再次导航
    if "AdvSearch" not in page.url:
        await page.goto("https://kns.cnki.net/kns8s/AdvSearch", timeout=30000)
        await asyncio.sleep(2)
        await wait_for_captcha(page)

    # ── 填写搜索表单 ──

    # 清空并填写第一个关键词
    try:
        # 第一个搜索条件：主题
        first_input = page.locator(
            ".search-box input[type='text']"
        ).first
        await first_input.click()
        await first_input.fill(task.keywords[0])
        await asyncio.sleep(0.3)
        # 按 Escape 关闭搜索建议下拉框
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)

        # 添加额外关键词条件
        for i, kw in enumerate(task.keywords[1:], start=1):
            # 点击"添加条件"按钮
            add_btn = page.locator("text=添加条件").first
            if await add_btn.is_visible():
                await add_btn.click()
                await asyncio.sleep(0.5)

            # 点击空白处关闭可能的下拉框
            await page.click("body", position={"x": 10, "y": 10})
            await asyncio.sleep(0.3)

            # 在新增的输入框中填写
            inputs = page.locator(
                ".search-box input[type='text']"
            )
            count = await inputs.count()
            if count > i:
                target = inputs.nth(i)
                await target.scroll_into_view_if_needed()
                await target.click(force=True)
                await target.fill(kw)
                await asyncio.sleep(0.3)
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.2)

        # 设置日期范围
        try:
            date_from = page.locator(
                "input[placeholder*='开始'], input.publishdate_from"
            ).first
            if await date_from.is_visible(timeout=2000):
                await date_from.fill(str(task.start_year))

            date_to = page.locator(
                "input[placeholder*='结束'], input.publishdate_to"
            ).first
            if await date_to.is_visible(timeout=2000):
                await date_to.fill(str(task.end_year))
        except Exception:
            print("  (日期过滤可能需要手动设置)")

        # 点击搜索按钮
        search_btn = page.locator(
            "input[type='submit'], button.search-btn, "
            "input.btnSearch, .search-btn"
        ).first
        await search_btn.click()

    except Exception as e:
        # 表单操作失败，直接用 URL 参数搜索
        print(f"  高级搜索表单失败，切换到URL搜索...")
        src_codes = _resolve_source_codes(task.source_types)
        from urllib.parse import quote
        # 多关键词用空格拼接，kns8s 的 kw 参数支持空格分词 AND 搜索
        combined = " ".join(task.keywords)
        search_url = (
            f"https://kns.cnki.net/kns8s/defaultresult/index"
            f"?kw={quote(combined)}&korder=SU"
        )
        # 日期过滤
        if task.start_year:
            search_url += f"&date_from={task.start_year}"
        if task.end_year:
            search_url += f"&date_to={task.end_year}"
        # 文献类型过滤
        if src_codes:
            search_url += f"&bCKY3={src_codes}"
        await page.goto(search_url, timeout=30000)

    # 等待结果加载
    await asyncio.sleep(3)
    await wait_for_captcha(page)

    # ── 文献类型过滤：确保 URL 中包含数据库过滤参数 ──
    if task.source_types:
        src_codes = _resolve_source_codes(task.source_types)
        if src_codes and f"bCKY3={src_codes}" not in page.url:
            current_url = page.url
            # 移除已有的 bCKY3 参数
            clean_url = re.sub(r'[&?]bCKY3=[^&]*', '', current_url)
            sep = "&" if "?" in clean_url else "?"
            filtered_url = f"{clean_url}{sep}bCKY3={src_codes}"
            print(f"  应用文献类型过滤: {', '.join(task.source_types)} ({src_codes})")
            await page.goto(filtered_url, timeout=30000)
            await asyncio.sleep(3)
            await wait_for_captcha(page)

    # 等待结果表格出现
    try:
        await page.wait_for_selector(
            "table.result-table-list, .result-table-list, #gridTable",
            timeout=15000,
        )
    except Exception:
        # 可能没有结果或页面结构不同
        print("  未找到结果表格，尝试等待更长时间...")
        await asyncio.sleep(5)

    # ── 解析搜索结果 ──
    # 确定允许的 dbname 前缀（用于二次过滤）
    allowed_doc_types = _get_allowed_doc_types(task.source_types)

    papers = await parse_results(page)
    if allowed_doc_types:
        before = len(papers)
        papers = _filter_by_doc_type(papers, allowed_doc_types)
        if len(papers) < before:
            print(f"  -> 类型过滤: {before} -> {len(papers)} 篇 (排除非目标类型)")
    print(f"  -> 获取到 {len(papers)} 篇文献")

    # 如果已达上限，直接截断返回
    if limit > 0 and len(papers) >= limit:
        papers = papers[:limit]
        print(f"  -> 已达上限 {limit} 篇，停止翻页")
        return papers

    # 翻页获取更多（不限制时最多取前10页，约200篇）
    max_page = 10
    for next_page in range(2, max_page + 1):
        try:
            next_btn = page.locator(f"a[data-page='{next_page}']").first
            if not await next_btn.is_visible(timeout=2000):
                # 尝试 "下一页" 按钮
                next_btn = page.locator("a#PageNext, a.next").first
                if not await next_btn.is_visible(timeout=2000):
                    break

            await next_btn.click()
            await asyncio.sleep(3)
            await wait_for_captcha(page)

            more = await parse_results(page)
            if allowed_doc_types:
                more = _filter_by_doc_type(more, allowed_doc_types)
            if not more:
                break
            papers.extend(more)
            print(f"  -> 第{next_page}页: +{len(more)} 篇 (累计 {len(papers)})")

            # 检查是否已达上限
            if limit > 0 and len(papers) >= limit:
                papers = papers[:limit]
                print(f"  -> 已达上限 {limit} 篇，停止翻页")
                break
        except Exception:
            break

    return papers


async def parse_results(page) -> list[PaperInfo]:
    """解析当前页面的搜索结果。"""
    papers: list[PaperInfo] = []

    try:
        # kns8s 的结果表格
        rows = page.locator(
            "table.result-table-list tbody tr, "
            ".result-table-list tbody tr"
        )
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

                # 来源期刊
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

                # 提取 dbname 和 filename
                dbname = ""
                filename_val = ""
                if href:
                    db_m = re.search(r"dbname=(\w+)", href, re.IGNORECASE)
                    fn_m = re.search(r"filename=(\w+)", href, re.IGNORECASE)
                    if db_m:
                        dbname = db_m.group(1)
                    if fn_m:
                        filename_val = fn_m.group(1)

                # 文献类型（td.data 列：期刊、硕士、博士、会议 等）
                doc_type = ""
                try:
                    dtype_el = row.locator("td.data").first
                    doc_type = (await dtype_el.inner_text()).strip()
                except Exception:
                    pass

                if title:
                    papers.append(PaperInfo(
                        title=title,
                        authors=authors,
                        journal=journal,
                        publish_date=pub_date,
                        url=href,
                        dbname=dbname,
                        filename=filename_val,
                        doc_type=doc_type,
                    ))

            except Exception:
                continue

    except Exception as e:
        print(f"  解析结果失败: {e}")

    return papers


async def download_paper_pdf(
    page, context, paper: PaperInfo, output_dir: Path
) -> Path | None:
    """下载单篇文献的 PDF。"""
    if not paper.url:
        print(f"    [SKIP] 无URL: {paper.title[:40]}")
        return None

    detail_page = None
    try:
        # 打开文献详情页
        detail_page = await context.new_page()
        await detail_page.goto(paper.url, timeout=30000)
        await asyncio.sleep(2)
        await wait_for_captcha(detail_page)

        # ── 抓取摘要和关键词 ──
        try:
            abs_el = detail_page.locator(
                "#ChDivSummary, .abstract-text, span#ChDivSummary"
            ).first
            if await abs_el.is_visible(timeout=3000):
                paper.abstract = (await abs_el.inner_text()).strip()
        except Exception:
            pass
        try:
            kw_els = detail_page.locator(
                ".keywords a, p.keywords a"
            )
            kw_count = await kw_els.count()
            if kw_count > 0:
                paper.keywords = [
                    (await kw_els.nth(k).inner_text()).strip().rstrip(";；")
                    for k in range(kw_count)
                ]
        except Exception:
            pass

        safe_title = re.sub(r'[<>:"/\\|?*]', '_', paper.title)[:80]
        output_path = output_dir / f"{safe_title}.pdf"

        # 如果文件已存在，跳过（但仍需抓取元数据）
        if output_path.exists():
            print(f"    [OK] 已存在: {safe_title}")
            await detail_page.close()
            return output_path

        # 查找PDF下载按钮（多种选择器）
        pdf_btn = None
        selectors = [
            "a#pdfDown",
            "a.btn-dlpdf",
            "a:has-text('PDF下载')",
            "a:has-text('整本下载')",
            "a[href*='PDF']",
            "a:has-text('下载')",
        ]
        for sel in selectors:
            try:
                el = detail_page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    pdf_btn = el
                    break
            except Exception:
                continue

        if not pdf_btn:
            print(f"    [FAIL] 未找到下载按钮: {safe_title}")
            await detail_page.close()
            return None

        # 尝试获取下载链接的href，先直接导航下载
        href = await pdf_btn.get_attribute("href")

        # 方法1: 直接通过 expect_download 事件捕获下载
        try:
            async with detail_page.expect_download(timeout=30000) as dl_info:
                await pdf_btn.click()
            download = await dl_info.value
            await download.save_as(str(output_path))
            print(f"    [OK] {safe_title}")
            await detail_page.close()
            return output_path
        except Exception:
            pass

        # 方法2: 点击后可能打开新标签页（需要登录）
        try:
            # 检查是否打开了新页面
            pages = context.pages
            if len(pages) > 2:  # main + detail + new
                new_page = pages[-1]
                # 等待看是否是下载
                await asyncio.sleep(3)
                if "login" in new_page.url.lower():
                    print(f"    [FAIL] 需要登录: {safe_title}")
                    await new_page.close()
                else:
                    # 可能是在线阅读页面
                    print(f"    [FAIL] 无法直接下载: {safe_title}")
                    await new_page.close()
        except Exception:
            pass

        await detail_page.close()
        return None

    except Exception as e:
        err_msg = str(e)[:60]
        print(f"    [FAIL] {paper.title[:30]}... ({err_msg})")
        if detail_page:
            try:
                await detail_page.close()
            except Exception:
                pass
        return None


def generate_bibtex(papers: list[PaperInfo]) -> str:
    """从 PaperInfo 列表生成 BibTeX 格式字符串。"""
    entries: list[str] = []
    for paper in papers:
        # 生成 cite key: 第一作者 + 年份 + 标题前几字
        first_author = paper.authors[0] if paper.authors else "unknown"
        author_part = re.sub(r"[^a-zA-Z\u4e00-\u9fff]", "", first_author)[:10]
        year_match = re.search(r"(\d{4})", paper.publish_date)
        year = year_match.group(1) if year_match else ""
        title_words = re.findall(r"[\w\u4e00-\u9fff]+", paper.title)[:2]
        title_part = "".join(title_words)[:15]
        key = f"{author_part}{year}{title_part}"

        authors_str = " and ".join(paper.authors) if paper.authors else "Unknown"

        lines = [
            f"@article{{{key},",
            f"  title = {{{paper.title}}},",
            f"  author = {{{authors_str}}},",
        ]
        if paper.journal:
            lines.append(f"  journal = {{{paper.journal}}},")
        if year:
            lines.append(f"  year = {{{year}}},")
        if paper.keywords:
            lines.append(f"  keywords = {{{', '.join(paper.keywords)}}},")
        if paper.abstract:
            lines.append(f"  abstract = {{{paper.abstract}}},")
        if paper.url:
            lines.append(f"  url = {{{paper.url}}},")
        lines.append("}")
        entries.append("\n".join(lines))

    return "\n\n".join(entries)


def save_bibtex(papers: list[PaperInfo], output_dir: Path, task_name: str) -> Path:
    """将搜索结果保存为 BibTeX 文件到对应目录。"""
    content = generate_bibtex(papers)
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', task_name)
    bib_path = output_dir / f"{safe_name}.bib"
    bib_path.write_text(content, encoding="utf-8")
    return bib_path


def save_csv(papers: list[PaperInfo], output_dir: Path, task_name: str) -> Path:
    """将搜索结果保存为 CSV 文件（题名、作者、年份、期刊、摘要、关键词）。"""
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', task_name)
    csv_path = output_dir / f"{safe_name}.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["题名", "作者", "年份", "期刊", "摘要", "关键词"])
        for p in papers:
            year_match = re.search(r"(\d{4})", p.publish_date)
            year = year_match.group(1) if year_match else p.publish_date
            writer.writerow([
                p.title,
                "; ".join(p.authors),
                year,
                p.journal,
                p.abstract,
                "; ".join(p.keywords),
            ])
    return csv_path


def save_summary(
    all_results: dict[str, list[PaperInfo]], output_dir: Path
) -> Path:
    """保存所有搜索结果到 JSON 汇总文件。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for name, papers in all_results.items():
        papers_data = []
        for p in papers:
            papers_data.append({
                "title": p.title,
                "authors": p.authors,
                "journal": p.journal,
                "publish_date": p.publish_date,
                "url": p.url,
                "dbname": p.dbname,
                "filename": p.filename,
            })
        summary.append({
            "search_name": name,
            "papers_count": len(papers),
            "papers": papers_data,
        })

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"search_results_{ts}.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return json_path


def print_summary_table(all_results: dict[str, list[PaperInfo]]) -> None:
    """打印汇总表格。"""
    print("\n" + "=" * 70)
    print("  搜索结果汇总")
    print("=" * 70)
    print(f"  {'搜索主题':<35} {'文献数':>6}")
    print("  " + "-" * 45)
    total = 0
    for name, papers in all_results.items():
        print(f"  {name:<35} {len(papers):>6}")
        total += len(papers)
    print("  " + "-" * 45)
    print(f"  {'合计':<35} {total:>6}")
    print("=" * 70)


def load_saved_cookies() -> str | None:
    """加载已保存的浏览器状态(cookies)。"""
    if COOKIE_FILE.exists():
        try:
            data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
            # 检查是否有 cookies
            if data.get("cookies"):
                print(f"  [OK] 加载已保存的 Cookie ({len(data['cookies'])} 条)")
                return str(COOKIE_FILE)
        except Exception:
            pass
    return None


async def save_cookies(context) -> None:
    """保存浏览器 Cookie 到本地文件。"""
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = await context.storage_state(path=str(COOKIE_FILE))
    cookie_count = len(state.get("cookies", []))
    print(f"  [OK] Cookie 已保存 ({cookie_count} 条) -> {COOKIE_FILE}")


async def is_session_valid(page) -> bool:
    """检查当前 Cookie 是否仍然有效（未被重定向到验证页面）。"""
    try:
        await page.goto("https://kns.cnki.net/kns8s/", timeout=15000)
        await asyncio.sleep(2)
        # 如果在验证页面或登录页面，说明 Cookie 失效
        url = page.url
        return "verify" not in url and "login" not in url
    except Exception:
        return False


async def main() -> None:
    from playwright.async_api import async_playwright

    max_label = f"{DEFAULT_MAX_PAPERS} 篇/主题" if DEFAULT_MAX_PAPERS > 0 else "不限制"
    print("\n" + "=" * 60)
    print("  CNKI 文献自动搜索与下载")
    print(f"  下载目录: {OUTPUT_DIR}")
    print(f"  数量上限: {max_label}")
    print(f"  Cookie:   {COOKIE_FILE}")
    print("  (首次需手动过验证，之后自动使用保存的Cookie)")
    print("  (--output <路径> 自定义下载目录)")
    print("  (--max <数量> 限制每个主题的最大文献数)")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        # 检查是否有已保存的 Cookie
        saved_state = load_saved_cookies()

        # 先尝试无头模式 + 已保存的 Cookie
        headless = saved_state is not None
        if headless:
            print("  尝试使用已保存的 Cookie (无头模式)...")

        browser = await pw.chromium.launch(
            headless=headless,
            slow_mo=200,
        )

        ctx_kwargs = {
            "accept_downloads": True,
            "viewport": {"width": 1400, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        if saved_state:
            ctx_kwargs["storage_state"] = saved_state

        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()

        # 验证 Cookie 是否有效
        if saved_state:
            if await is_session_valid(page):
                print("  [OK] Cookie 有效，无需验证！\n")
            else:
                # Cookie 失效，关掉无头浏览器，重新以有头模式打开
                print("  Cookie 已失效，切换到有头模式让用户验证...\n")
                await browser.close()

                browser = await pw.chromium.launch(
                    headless=False, slow_mo=300
                )
                del ctx_kwargs["storage_state"]
                context = await browser.new_context(**ctx_kwargs)
                page = await context.new_page()

                print("  正在打开知网...")
                await page.goto("https://www.cnki.net", timeout=30000)
                await asyncio.sleep(2)
                await wait_for_captcha(page)
                # 保存新的 Cookie
                await save_cookies(context)
        else:
            # 没有保存的 Cookie，直接以有头模式打开
            print("\n  正在打开知网...")
            await page.goto("https://www.cnki.net", timeout=30000)
            await asyncio.sleep(2)
            await wait_for_captcha(page)
            # 保存 Cookie
            await save_cookies(context)

        # ── Phase 1: 执行所有搜索 ──
        all_results: dict[str, list[PaperInfo]] = {}

        for i, task in enumerate(TASKS, 1):
            print(f"\n  [{i}/{len(TASKS)}] 搜索中...")
            try:
                papers = await do_search(page, task)
                all_results[task.name] = papers

                if papers:
                    # 显示前几条结果
                    for j, p in enumerate(papers[:5], 1):
                        authors = ", ".join(p.authors[:3])
                        if len(p.authors) > 3:
                            authors += " 等"
                        print(
                            f"    {j}. {p.title[:50]}"
                            f"  [{authors}]  {p.journal}  {p.publish_date}"
                        )
                    if len(papers) > 5:
                        print(f"    ... 共 {len(papers)} 篇")

                # 搜索间稍等，避免触发反爬
                await asyncio.sleep(3)

            except Exception as e:
                print(f"  搜索失败: {e}")
                all_results[task.name] = []

        # 搜索完成后刷新保存 Cookie
        await save_cookies(context)

        # ── Phase 2: 保存搜索结果 ──
        print_summary_table(all_results)

        json_path = save_summary(all_results, OUTPUT_DIR)
        print(f"\n  搜索结果已保存: {json_path}")

        # ── Phase 3: 下载 PDF ──
        total_papers = sum(len(ps) for ps in all_results.values())
        if total_papers == 0:
            print("\n  没有搜索到任何文献，跳过下载。")
            await browser.close()
            return

        print(f"\n  即将下载 {total_papers} 篇文献的 PDF...")
        print("  (需要校园网或已登录知网账号才能下载全文)")
        print("  按 Ctrl+C 可中断下载（搜索结果已保存到JSON）\n")

        downloaded_count = 0
        failed_count = 0

        for task_name, papers in all_results.items():
            if not papers:
                continue

            # 每个搜索任务一个子目录
            safe_dir = re.sub(r'[<>:"/\\|?*]', '_', task_name)
            task_dir = OUTPUT_DIR / safe_dir
            task_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n  下载: {task_name} ({len(papers)} 篇) -> {task_dir}")

            for j, paper in enumerate(papers, 1):
                print(f"  [{j}/{len(papers)}] {paper.title[:50]}...")
                result = await download_paper_pdf(
                    page, context, paper, task_dir
                )
                if result:
                    downloaded_count += 1
                else:
                    failed_count += 1

                # 下载间隔
                await asyncio.sleep(2)

            # 保存 BibTeX 和 CSV 文件到任务目录
            bib_path = save_bibtex(papers, task_dir, task_name)
            print(f"  [OK] BibTeX 已保存: {bib_path}")
            csv_path = save_csv(papers, task_dir, task_name)
            print(f"  [OK] CSV 已保存: {csv_path}")

        # ── Phase 4: 最终汇总 ──
        print("\n" + "=" * 60)
        print("  下载完成汇总")
        print(f"  成功: {downloaded_count}  失败: {failed_count}")
        print(f"  文件保存在: {OUTPUT_DIR}")
        print("=" * 60 + "\n")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
