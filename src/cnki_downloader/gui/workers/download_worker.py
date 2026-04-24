"""下载后台线程 — 使用 Playwright 浏览器下载 PDF"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from cnki_downloader.core.downloader import build_filename
from cnki_downloader.models.paper import Paper


def _get_cookie_file() -> Path:
    try:
        from cnki_downloader.utils.config import get_config_dir
        return get_config_dir() / "browser_state.json"
    except Exception:
        return Path.home() / ".cnki_downloader" / "browser_state.json"


class DownloadWorker(QThread):
    """后台下载线程，通过 Playwright 浏览器下载 PDF。"""

    progress = pyqtSignal(str, int, int)           # task_id, downloaded, total
    file_completed = pyqtSignal(str, str)           # task_id, file_path
    file_error = pyqtSignal(str, str)               # task_id, error_msg
    all_finished = pyqtSignal(list)                  # list[str] 所有完成的路径
    error = pyqtSignal(str)

    def __init__(
        self,
        papers: list[Paper],
        output_dir: Path,
        max_concurrent: int = 3,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._papers = papers
        self._output_dir = output_dir
        self._max_concurrent = max_concurrent

    def run(self) -> None:
        try:
            paths = asyncio.run(self._download_all())
            self.all_finished.emit([str(p) for p in paths])
        except Exception as e:
            self.error.emit(str(e))

    async def _download_all(self) -> list[Path]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "下载需要 Playwright，请运行：\n"
                "pip install playwright && python -m playwright install chromium"
            )

        cookie_file = _get_cookie_file()
        ctx_kwargs = {
            "accept_downloads": True,
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

        self._output_dir.mkdir(parents=True, exist_ok=True)
        completed: list[Path] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(**ctx_kwargs)

            for i, paper in enumerate(self._papers):
                task_id = paper.filename or paper.title
                self.progress.emit(task_id, 0, 100)

                try:
                    path = await self._download_one(
                        context, paper, self._output_dir
                    )
                    if path:
                        completed.append(path)
                        self.file_completed.emit(task_id, str(path))
                    else:
                        self.file_error.emit(task_id, "未找到下载链接或需要登录")
                except Exception as e:
                    from cnki_downloader.core.exceptions import CaptchaRequiredError

                    if isinstance(e, CaptchaRequiredError):
                        # 验证码：关闭无头浏览器，用可见浏览器让用户完成验证
                        await browser.close()
                        browser = await pw.chromium.launch(headless=False)
                        context = await browser.new_context(**ctx_kwargs)
                        self.file_error.emit(
                            task_id,
                            "检测到验证码，已打开浏览器窗口，请完成验证后自动继续",
                        )
                        # 重试当前论文
                        try:
                            path = await self._download_one(
                                context, paper, self._output_dir
                            )
                            if path:
                                completed.append(path)
                                self.file_completed.emit(task_id, str(path))
                        except Exception as retry_e:
                            self.file_error.emit(task_id, str(retry_e)[:100])
                    else:
                        self.file_error.emit(task_id, str(e)[:100])

                # 下载间隔
                await asyncio.sleep(1.5)

            await browser.close()

        return completed

    async def _download_one(
        self, context, paper: Paper, output_dir: Path
    ) -> Path | None:
        """下载单篇文献 PDF。"""
        if not paper.url:
            return None

        detail_page = await context.new_page()
        try:
            await detail_page.goto(paper.url, timeout=30000)
            await asyncio.sleep(2)

            # 检查验证码：自动等待用户在浏览器中完成验证
            if "verify" in detail_page.url:
                from cnki_downloader.core.exceptions import CaptchaRequiredError

                try:
                    await detail_page.wait_for_url(
                        lambda url: "verify" not in url,
                        timeout=120_000,
                    )
                    await asyncio.sleep(1)
                except Exception:
                    raise CaptchaRequiredError(
                        "知网验证超时，请先通过「机构登录」完成认证"
                    )

            safe_name = build_filename(paper, max_length=80)
            output_path = output_dir / f"{safe_name}.pdf"

            # 已存在则跳过
            if output_path.exists():
                return output_path

            # 查找 PDF 下载按钮
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
                return None

            # 尝试下载
            try:
                async with detail_page.expect_download(timeout=30000) as dl_info:
                    await pdf_btn.click()
                download = await dl_info.value
                await download.save_as(str(output_path))
                return output_path
            except Exception:
                pass

            # 检查是否打开了新标签
            try:
                pages = context.pages
                if len(pages) > 2:
                    new_page = pages[-1]
                    await asyncio.sleep(2)
                    if "login" in new_page.url.lower():
                        await new_page.close()
                        raise RuntimeError("需要登录")
                    await new_page.close()
            except RuntimeError:
                raise
            except Exception:
                pass

            return None
        finally:
            try:
                await detail_page.close()
            except Exception:
                pass
