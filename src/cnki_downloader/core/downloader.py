"""下载引擎：批量下载、断点续传、并发控制"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Protocol

from cnki_downloader.core.exceptions import DownloadError
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.paper import Paper

logger = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """进度回调协议 — GUI和CLI分别实现"""

    def on_progress(self, task_id: str, downloaded: int, total: int) -> None: ...
    def on_complete(self, task_id: str, file_path: Path) -> None: ...
    def on_error(self, task_id: str, error: Exception) -> None: ...


class NullProgress:
    """空进度回调，用于不需要进度显示的场景。"""

    def on_progress(self, task_id: str, downloaded: int, total: int) -> None:
        pass

    def on_complete(self, task_id: str, file_path: Path) -> None:
        pass

    def on_error(self, task_id: str, error: Exception) -> None:
        pass


def paper_from_url(url: str) -> Paper:
    """从 CNKI 详情页 URL 解析出一个最小化的 Paper。

    尽力从 querystring 中提取 dbname/dbcode 与 filename，以便后续命名
    和直连下载都能拿到唯一标识，避免所有 URL 下载统一命名为 "download"。
    """
    # 知网 URL 里 dbname 和 dbcode 都可能出现，dbname 更完整（如 CJFDLAST），dbcode 是短码（CJFD）
    dbname_match = re.search(r"[?&]dbname=([^&#]+)", url, re.IGNORECASE) or re.search(
        r"[?&]dbcode=([^&#]+)", url, re.IGNORECASE
    )
    filename_match = re.search(r"[?&]filename=([^&#]+)", url, re.IGNORECASE)
    dbname = dbname_match.group(1) if dbname_match else ""
    filename = filename_match.group(1) if filename_match else ""
    title = filename or "download"
    return Paper(title=title, url=url, dbname=dbname, filename=filename)


def _build_direct_download_url(paper: Paper, fmt: str = "pdf") -> str | None:
    """尝试从 dbname + filename 直接构造下载 URL，跳过详情页访问。

    借鉴 jasminum 的思路：CNKI 下载链接模式是可预测的，
    不必每次都访问详情页再解析 DOM。
    """
    if not paper.dbname or not paper.filename:
        return None

    # 知网 PDF/CAJ 下载的标准 URL 模式
    if fmt == "pdf":
        return (
            f"https://kns.cnki.net/KXReader/Detail"
            f"?dbcode={paper.dbname}&filename={paper.filename}"
            f"&uid=&p=&cflag=overlay"
        )
    return None


async def get_download_url(session: SessionManager, paper: Paper) -> str:
    """获取文献 PDF 下载链接。

    优先尝试从 dbname+filename 直接构造 URL（快速路径），
    失败时回退到详情页解析（兼容路径）。
    """
    # 快速路径：直接构造下载 URL
    direct_url = _build_direct_download_url(paper)
    if direct_url:
        try:
            resp = await session.head(direct_url)
            content_type = resp.headers.get("content-type", "")
            if resp.status_code == 200 and (
                "pdf" in content_type.lower()
                or "octet-stream" in content_type.lower()
                or "caj" in content_type.lower()
            ):
                logger.info("直接构造下载URL成功: %s", direct_url)
                return direct_url
        except Exception:
            logger.debug("直接构造URL失败，回退到详情页解析")

    # 回退路径：从详情页提取下载链接
    if not paper.url:
        raise DownloadError(f"文献 '{paper.title}' 没有详情页URL")

    resp = await session.get(paper.url)
    resp.raise_for_status()

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(resp.text, "lxml")

    # 知网详情页上的PDF下载按钮
    pdf_link = soup.find("a", id="pdfDown") or soup.find(
        "a", attrs={"href": re.compile(r".*\.pdf.*", re.IGNORECASE)}
    )

    if not pdf_link:
        # 尝试CAJ下载链接
        caj_link = soup.find("a", id="cajDown")
        if caj_link:
            href = caj_link.get("href", "")
            if href and not href.startswith("http"):
                href = "https://kns.cnki.net" + href
            return href
        raise DownloadError(f"未找到文献 '{paper.title}' 的下载链接")

    href = pdf_link.get("href", "")
    if href and not href.startswith("http"):
        href = "https://kns.cnki.net" + href
    return href


async def download_paper(
    session: SessionManager,
    paper: Paper,
    output_dir: Path,
    progress: ProgressCallback | None = None,
    resume: bool = True,
) -> Path:
    """下载单篇文献到指定目录，支持断点续传。

    Args:
        session: HTTP会话管理器
        paper: 文献对象
        output_dir: 输出目录
        progress: 进度回调
        resume: 是否启用断点续传

    Returns:
        下载完成的文件路径
    """
    if progress is None:
        progress = NullProgress()

    task_id = paper.filename or paper.title

    try:
        download_url = await get_download_url(session, paper)
        logger.info("开始下载: %s -> %s", paper.title, download_url)

        # 用 HEAD 请求获取文件信息，避免下载整个文件
        content_type = ""
        total = 0
        try:
            head_resp = await session.head(download_url)
            content_type = head_resp.headers.get("content-type", "")
            total = int(head_resp.headers.get("content-length", 0))
        except Exception as e:
            logger.warning("HEAD preflight failed; fallback to stream metadata: %s", e)

        # 推断文件扩展名
        if "pdf" in content_type.lower():
            ext = ".pdf"
        elif "caj" in content_type.lower() or download_url.lower().endswith(".caj"):
            ext = ".caj"
        else:
            ext = ".pdf"

        # 构造安全文件名：作者（年份）前三个单词
        safe_name = build_filename(paper)
        output_path = output_dir / f"{safe_name}{ext}"
        partial_path = output_dir / f"{safe_name}{ext}.part"

        output_dir.mkdir(parents=True, exist_ok=True)

        # 断点续传：检查已下载的部分
        downloaded = 0
        headers = {}
        if resume and partial_path.exists():
            downloaded = partial_path.stat().st_size
            if total and downloaded < total:
                headers["Range"] = f"bytes={downloaded}-"
                logger.info("断点续传: 已下载 %d / %d 字节", downloaded, total)
            elif total and downloaded >= total:
                # 文件已完整下载
                partial_path.rename(output_path)
                progress.on_complete(task_id, output_path)
                return output_path

        resp = await session.stream_download(download_url, headers=headers)
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("location", "")
            raise DownloadError(f"Download redirected unexpectedly: {location}")
        if resp.status_code >= 400:
            raise DownloadError(f"Download failed with HTTP status {resp.status_code}")

        # 如果服务器不支持Range请求，重头开始
        if resp.status_code == 200:
            downloaded = 0
            total = int(resp.headers.get("content-length", 0))
        elif resp.status_code == 206:
            # Partial Content，续传成功
            content_range = resp.headers.get("content-range", "")
            if content_range:
                range_total = content_range.split("/")[-1]
                if range_total.isdigit():
                    total = int(range_total)

        mode = "ab" if downloaded > 0 else "wb"

        try:
            with open(partial_path, mode) as f:
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    progress.on_progress(task_id, downloaded, total)
        finally:
            await resp.aclose()

        # 下载完成，重命名
        partial_path.rename(output_path)

        logger.info("下载完成: %s", output_path)
        progress.on_complete(task_id, output_path)
        return output_path

    except Exception as e:
        error = DownloadError(f"下载失败: {e}")
        progress.on_error(task_id, error)
        raise error from e


async def batch_download(
    session: SessionManager,
    papers: list[Paper],
    output_dir: Path,
    progress: ProgressCallback | None = None,
    max_concurrent: int = 3,
    auto_convert: bool = True,
) -> list[Path]:
    """批量下载文献，支持并发控制。

    Args:
        session: HTTP会话管理器
        papers: 文献列表
        output_dir: 输出目录
        progress: 进度回调
        max_concurrent: 最大并发数
        auto_convert: 是否自动将CAJ转为PDF

    Returns:
        成功下载的文件路径列表
    """
    if progress is None:
        progress = NullProgress()

    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[Path] = []
    errors: list[tuple[Paper, Exception]] = []

    async def _download_one(paper: Paper) -> None:
        async with semaphore:
            try:
                path = await download_paper(session, paper, output_dir, progress)
                # 自动CAJ转PDF
                if auto_convert and path.suffix.lower() == ".caj":
                    try:
                        from cnki_downloader.core.converter import convert_caj_to_pdf

                        pdf_path = convert_caj_to_pdf(path, delete_caj=True)
                        results.append(pdf_path)
                    except Exception as ce:
                        logger.warning("CAJ转PDF失败: %s, 保留CAJ文件", ce)
                        results.append(path)
                else:
                    results.append(path)
            except Exception as e:
                errors.append((paper, e))
                logger.error("下载失败 [%s]: %s", paper.title, e)

    tasks = [asyncio.create_task(_download_one(p)) for p in papers]
    await asyncio.gather(*tasks)

    if errors:
        logger.warning("批量下载完成: %d 成功, %d 失败", len(results), len(errors))
    else:
        logger.info("批量下载全部完成: %d 篇", len(results))

    return results


def _sanitize_filename(name: str, max_length: int = 100) -> str:
    """清理文件名中的非法字符。"""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    if len(name) > max_length:
        name = name[:max_length]
    return name or "untitled"


_TITLE_SPLIT_RE = re.compile(r"[\s\-_:：;；,，、/\\|]+")


def _first_words(title: str, count: int = 3) -> str:
    """取标题前 N 个"单词"。空格分隔时按空格切；中文标题无空格时回退到前若干字符。"""
    title = (title or "").strip()
    if not title:
        return ""
    tokens = [t for t in _TITLE_SPLIT_RE.split(title) if t]
    if len(tokens) >= 2:
        return " ".join(tokens[:count])
    # 无可切分空白：整条标题留给 max_length 截断
    return title


def build_filename(paper: Paper, max_length: int = 100) -> str:
    """按 "作者(年份) 前三个单词" 规则构造下载文件名。

    缺失字段时逐级回退，最后兜底到 CNKI filename / "untitled"，
    保证批量下载时每篇论文都能拿到可区分的文件名，而不是统一叫 "download"。
    """
    author = paper.authors[0].strip() if paper.authors else ""
    year = ""
    if paper.publish_date:
        m = re.search(r"(\d{4})", paper.publish_date)
        if m:
            year = m.group(1)

    prefix = ""
    if author and year:
        prefix = f"{author}({year})"
    elif author:
        prefix = author
    elif year:
        prefix = f"({year})"

    title_part = _first_words(paper.title)

    if prefix and title_part:
        name = f"{prefix} {title_part}"
    else:
        name = prefix or title_part

    if not name:
        # 最后兜底：CNKI 内部标识一定是唯一的
        name = paper.cnki_id or paper.filename or "untitled"

    return _sanitize_filename(name, max_length=max_length)
