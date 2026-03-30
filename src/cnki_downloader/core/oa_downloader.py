import logging
import os
import re
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
import httpx
import requests
from bs4 import BeautifulSoup
from typing import Optional

# ======================================================================
# === 全局配置区域 (请在此处填写备选服务的具体信息) ===
# ======================================================================

# --- 备选下载器配置 ---
# 如果 oa_downloader 找不到开放获取资源，将使用此配置
FALLBACK_SERVICE_NAME = "备用文献服务"  # 服务名称
FALLBACK_INDEX_URL = "https://tool.yovisun.com/scihub/"  # 例如: 
FALLBACK_LINK_IDENTIFIER = "sci-hub"  # 例如: 'sci-hub' 或正则
FALLBACK_TIMEOUT_CONNECT = 10
FALLBACK_TIMEOUT_READ = 30

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================================================================
# === 第一部分：oa_downloader.py 核心逻辑 (保持原样) ===
# ======================================================================

class DownloadError(Exception):
    """自定义下载异常"""
    pass

@dataclass
class OpenAccessResult:
    """Resolved open-access PDF information."""
    provider: str
    pdf_url: str
    doi: str = ""
    title: str = ""
    landing_url: str = ""

def looks_like_doi(text: str) -> bool:
    """Return True when text resembles a DOI."""
    _DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
    return bool(_DOI_RE.match(normalize_doi(text)))

def normalize_doi(text: str) -> str:
    """Normalize raw DOI input."""
    cleaned = (text or "").strip()
    if cleaned.lower().startswith("https://doi.org/"):
        cleaned = cleaned[16:]
    if cleaned.lower().startswith("http://doi.org/"):
        cleaned = cleaned[15:]
    if cleaned.lower().startswith("doi:"):
        cleaned = cleaned[4:]
    return cleaned.strip()

@asynccontextmanager
async def _client_scope(client: Optional[httpx.AsyncClient]):
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(25.0),
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/xml,application/xml,text/html,*/*",
        },
    ) as scoped_client:
        yield scoped_client

async def resolve_open_access_pdf(
    *,
    doi: str = "",
    title: str = "",
    unpaywall_email: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> OpenAccessResult:
    """Resolve a downloadable OA PDF URL from DOI/title."""
    normalized_doi = normalize_doi(doi)
    normalized_title = (title or "").strip()
    
    if not normalized_doi and not normalized_title:
        raise DownloadError("Please provide DOI or title for English paper download")

    email = (
        (unpaywall_email or "").strip()
        or os.environ.get("CNKI_UNPAYWALL_EMAIL", "").strip()
        or "open-access@example.com"
    )

    async with _client_scope(client) as http_client:
        if not normalized_doi and normalized_title:
            try:
                doi_hit = await _lookup_doi_by_title_crossref(http_client, normalized_title)
            except Exception as exc:
                logger.debug("DOI-by-title lookup failed: %s", exc)
                doi_hit = None
            if doi_hit:
                normalized_doi = doi_hit["doi"]
                if doi_hit.get("title"):
                    normalized_title = doi_hit["title"]

        if normalized_doi:
            for lookup in (
                _lookup_unpaywall,
                _lookup_crossref_pdf_by_doi,
                _lookup_europepmc_pdf_by_doi,
            ):
                try:
                    hit = await lookup(http_client, normalized_doi, normalized_title, email)
                except Exception as exc:
                    logger.debug("OA provider failed (%s): %s", lookup.__name__, exc)
                    continue
                if hit:
                    return hit

        if normalized_title:
            try:
                arxiv_hit = await _lookup_arxiv_pdf_by_title(http_client, normalized_title)
            except Exception as exc:
                logger.debug("arXiv lookup failed: %s", exc)
                arxiv_hit = None
            if arxiv_hit:
                return arxiv_hit

    raise DownloadError(
        "No open-access PDF source found. Try another DOI/title or provide a valid DOI."
    )

async def download_open_access_pdf(
    result: OpenAccessResult,
    output_dir: Path,
    *,
    filename: str = "",
    client: httpx.AsyncClient | None = None,
) -> Path:
    """Download resolved OA PDF to disk."""
    if not result.pdf_url:
        raise DownloadError("No PDF URL available for download")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = _build_filename(result, filename)
    target_path = _next_available_path(output_dir / base_name)

    async with _client_scope(client) as http_client:
        resp = await http_client.get(result.pdf_url, follow_redirects=True)
        resp.raise_for_status()
        content = resp.content
        content_type = (resp.headers.get("content-type") or "").lower()

        if not _looks_like_pdf(resp.url.path, content, content_type):
            raise DownloadError("Resolved URL did not return PDF content")

        target_path.write_bytes(content)
        return target_path

def _build_filename(result: OpenAccessResult, requested_name: str) -> str:
    raw_name = (requested_name or "").strip()
    if not raw_name:
        raw_name = (result.title or result.doi or "english_paper").strip()
    safe = re.sub(r'[<>:"/\\|?*]', "_", raw_name).strip(". ")
    if not safe:
        safe = "english_paper"
    if not safe.lower().endswith(".pdf"):
        safe = f"{safe}.pdf"
    return safe[:180]

def _next_available_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 10_000):
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise DownloadError("Could not allocate output file path")

def _looks_like_pdf(path: str, content: bytes, content_type: str) -> bool:
    if content.startswith(b"%PDF-"):
        return True
    if "application/pdf" in content_type:
        return True
    return path.lower().endswith(".pdf")

# --- OA Lookup Functions ---
async def _lookup_unpaywall(
    client: httpx.AsyncClient,
    doi: str,
    title: str,
    email: str,
) -> Optional[OpenAccessResult]:
    url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}"
    resp = await client.get(url, params={"email": email})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    best = data.get("best_oa_location") or {}
    candidates = []
    if isinstance(best, dict):
        candidates.append(best)
    for loc in data.get("oa_locations") or []:
        if isinstance(loc, dict):
            candidates.append(loc)
    for location in candidates:
        pdf_url = (location.get("url_for_pdf") or "").strip()
        if pdf_url:
            return OpenAccessResult(
                provider="unpaywall",
                pdf_url=pdf_url,
                doi=doi,
                title=(title or data.get("title") or "").strip(),
                landing_url=(location.get("url") or "").strip(),
            )
    return None

async def _lookup_crossref_pdf_by_doi(
    client: httpx.AsyncClient,
    doi: str,
    title: str,
    email: str,
) -> Optional[OpenAccessResult]:
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    resp = await client.get(url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    message = (resp.json() or {}).get("message") or {}
    for link in message.get("link") or []:
        if not isinstance(link, dict):
            continue
        link_url = (link.get("URL") or "").strip()
        link_type = str(link.get("content-type") or "").lower()
        if link_url and ("pdf" in link_type or link_url.lower().endswith(".pdf")):
            return OpenAccessResult(
                provider="crossref",
                pdf_url=link_url,
                doi=doi,
                title=(title or _first_title(message) or "").strip(),
                landing_url=(message.get("URL") or "").strip(),
            )
    primary = ((message.get("resource") or {}).get("primary") or {}).get("URL")
    if isinstance(primary, str) and primary.lower().endswith(".pdf"):
        return OpenAccessResult(
            provider="crossref",
            pdf_url=primary.strip(),
            doi=doi,
            title=(title or _first_title(message) or "").strip(),
            landing_url=(message.get("URL") or "").strip(),
        )
    return None

async def _lookup_europepmc_pdf_by_doi(
    client: httpx.AsyncClient,
    doi: str,
    title: str,
    email: str,
) -> Optional[OpenAccessResult]:
    resp = await client.get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={"query": f'DOI:"{doi}"', "format": "json", "pageSize": "1"},
    )
    resp.raise_for_status()
    result_list = ((resp.json() or {}).get("resultList") or {}).get("result") or []
    if not result_list:
        return None
    first = result_list[0] if isinstance(result_list[0], dict) else {}
    pmcid = (first.get("pmcid") or "").strip()
    if not pmcid:
        return None
    pdf_url = f"https://europepmc.org/articles/{pmcid}?pdf=render"
    return OpenAccessResult(
        provider="europepmc",
        pdf_url=pdf_url,
        doi=doi,
        title=(title or first.get("title") or "").strip(),
        landing_url=f"https://europepmc.org/articles/{pmcid}",
    )

async def _lookup_doi_by_title_crossref(
    client: httpx.AsyncClient,
    title: str
) -> Optional[dict[str, str]]:
    resp = await client.get(
        "https://api.crossref.org/works",
        params={"query.title": title, "rows": "1", "select": "DOI,title"},
    )
    resp.raise_for_status()
    items = ((resp.json() or {}).get("message") or {}).get("items") or []
    if not items:
        return None
    first = items[0] if isinstance(items[0], dict) else {}
    doi = normalize_doi(str(first.get("DOI") or ""))
    if not doi:
        return None
    return {
        "doi": doi,
        "title": _first_title(first) or title,
    }

async def _lookup_arxiv_pdf_by_title(
    client: httpx.AsyncClient,
    title: str
) -> Optional[OpenAccessResult]:
    resp = await client.get(
        "https://export.arxiv.org/api/query",
        params={"search_query": f'ti:"{title}"', "start": "0", "max_results": "1"},
    )
    resp.raise_for_status()
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return None
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        return None
    entry_title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
    pdf_url = ""
    for link in entry.findall("atom:link", ns):
        href = (link.attrib.get("href") or "").strip()
        link_type = (link.attrib.get("type") or "").lower()
        link_title = (link.attrib.get("title") or "").lower()
        if href and (link_title == "pdf" or link_type == "application/pdf"):
            pdf_url = href
            break
    if not pdf_url:
        entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
        if "/abs/" in entry_id:
            pdf_url = entry_id.replace("/abs/", "/pdf/") + ".pdf"
    if not pdf_url:
        return None
    return OpenAccessResult(
        provider="arxiv",
        pdf_url=pdf_url,
        title=entry_title or title,
        landing_url=(entry.findtext("atom:id", default="", namespaces=ns) or "").strip(),
    )

def _first_title(payload: dict[str, object]) -> str:
    titles = payload.get("title")
    if isinstance(titles, list) and titles:
        return str(titles[0] or "")
    if isinstance(titles, str):
        return titles
    return ""

# ======================================================================
# === 第二部分：备选下载器 (原 Sci-Hub 逻辑，现已解耦) ===
# ======================================================================

class FallbackDownloader:
    """通用备选下载器，用于在OA资源不可用时尝试下载"""
    
    def __init__(self):
        self.available_links = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
        })

    def fetch_source_links(self):
        """从配置的索引页获取可用的下载源链接列表"""
        if not FALLBACK_INDEX_URL or FALLBACK_INDEX_URL.startswith("["):
            logger.error(f"错误: 请在全局变量中配置 FALLBACK_INDEX_URL")
            return False

        try:
            logger.info(f"正在访问索引页: {FALLBACK_INDEX_URL}")
            response = self.session.get(FALLBACK_INDEX_URL, timeout=FALLBACK_TIMEOUT_CONNECT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            found_links = []
            
            # 策略: 遍历所有链接，根据全局变量 LINK_IDENTIFIER 进行过滤
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link['href']
                # 判断逻辑：根据配置的标识符进行匹配
                if isinstance(FALLBACK_LINK_IDENTIFIER, str) and FALLBACK_LINK_IDENTIFIER.lower() in href.lower():
                    # 补全相对路径
                    if href.startswith('//'):
                        href = 'https:' + href
                    elif href.startswith('/'):
                        from urllib.parse import urlparse
                        parsed = urlparse(FALLBACK_INDEX_URL)
                        href = f"{parsed.scheme}://{parsed.netloc}{href}"
                    elif not href.startswith(('http://', 'https://')):
                        continue
                    found_links.append(href)
            
            # 去重
            self.available_links = list(set(found_links))
            if self.available_links:
                logger.info(f"从索引页发现 {len(self.available_links)} 个源链接")
                return True
            else:
                logger.warning("未在索引页找到匹配的链接，请检查 LINK_IDENTIFIER 配置")
                return False
                
        except Exception as e:
            logger.error(f"获取源链接失败: {e}")
            return False

    def find_working_endpoint(self):
        """测试并返回一个可用的下载端点"""
        if not self.available_links and not self.fetch_source_links():
            return None
        
        for link in self.available_links:
            try:
                test_response = self.session.head(link, timeout=FALLBACK_TIMEOUT_CONNECT, allow_redirects=True)
                if test_response.status_code < 500:
                    logger.info(f"使用备选端点: {link}")
                    return link
            except Exception as e:
                continue
        return None

    def download_resource(self, identifier: str, output_path: Path) -> bool:
        """下载资源"""
        working_endpoint = self.find_working_endpoint()
        if not working_endpoint:
            logger.error("无法连接到备选下载服务")
            return False
        
        try:
            target_url = f"{working_endpoint.rstrip('/')}/{identifier.lstrip('/')}"
            logger.info(f"备选下载请求: {target_url}")
            
            response = self.session.get(target_url, timeout=FALLBACK_TIMEOUT_READ)
            response.raise_for_status()

            # 简单的PDF检测或HTML解析逻辑
            if response.headers.get('Content-Type', '').lower() == 'application/pdf':
                content = response.content
            else:
                # 这里需要根据实际备选服务的HTML结构解析PDF链接
                # 由于不同服务结构不同，这里提供一个通用的iframe查找逻辑
                soup = BeautifulSoup(response.text, 'html.parser')
                pdf_frame = soup.find('iframe', {'src': True})
                if pdf_frame:
                    pdf_src = pdf_frame['src']
                    if not pdf_src.startswith('http'):
                        pdf_src = working_endpoint + pdf_src
                    pdf_resp = self.session.get(pdf_src)
                    content = pdf_resp.content
                else:
                    logger.error("无法从备选页面解析出PDF内容")
                    return False

            with open(output_path, 'wb') as f:
                f.write(content)
            logger.info(f"备选下载成功: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"备选下载失败: {e}")
            return False

# ======================================================================
# === 第三部分：主程序逻辑 ===
# ======================================================================

import asyncio

async def main():
    # 检查备选配置
    if FALLBACK_INDEX_URL.startswith("[") or FALLBACK_LINK_IDENTIFIER.startswith("["):
        print("==========================================")
        print("警告: 尚未配置备选下载器全局变量！")
        print("请在代码文件开头填写 FALLBACK_INDEX_URL 和 FALLBACK_LINK_IDENTIFIER 等信息。")
        print("==========================================")
        return

    # 获取用户输入
    user_input = input("请输入论文的DOI或标题: ").strip()
    output_dir = Path("./downloads")
    
    # 初始化下载器
    fallback_downloader = FallbackDownloader()
    
    try:
        # 阶段 1: 尝试 Open Access 下载
        print("\n[1/2] 正在尝试通过开放获取源下载...")
        result = None
        
        if looks_like_doi(user_input):
            result = await resolve_open_access_pdf(doi=user_input)
        else:
            result = await resolve_open_access_pdf(title=user_input)
        
        # 如果 OA 下载成功，直接返回
        if result and result.pdf_url:
            print(f"找到开放获取资源 ({result.provider}): {result.pdf_url}")
            await download_open_access_pdf(result, output_dir)
            return
            
    except DownloadError as de:
        print(f"开放获取下载失败: {de}")
        print("\n[2/2] 正在尝试通过备选服务下载...")
        
        # 阶段 2: OA 失败，降级使用备选下载器
        try:
            # 这里直接使用用户输入的原始字符串作为标识符
            filename = user_input.replace("/", "_") + ".pdf"
            success = fallback_downloader.download_resource(user_input, output_dir / filename)
            if not success:
                print("备选服务下载也失败了。")
        except Exception as e:
            print(f"备选服务下载异常: {e}")

if __name__ == "__main__":
    asyncio.run(main())