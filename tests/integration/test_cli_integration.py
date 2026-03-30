"""CLI集成测试 — 测试CLI命令的基本可用性"""

import subprocess
import sys


class TestCLIHelp:
    """验证所有CLI命令的help能正常输出。"""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "cnki_downloader", *args, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_root_help(self) -> None:
        result = self._run()
        assert result.returncode == 0
        assert "search" in result.stdout
        assert "download" in result.stdout
        assert "convert" in result.stdout
        assert "gui" in result.stdout
        assert "auth" in result.stdout
        assert "library" not in result.stdout

    def test_root_without_args_shows_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cnki_downloader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "search" in result.stdout
        assert "download" in result.stdout
        assert "convert" in result.stdout

    def test_search_help(self) -> None:
        result = self._run("search")
        assert result.returncode == 0
        assert "--author" in result.stdout
        assert "--journal" in result.stdout

    def test_download_help(self) -> None:
        result = self._run("download")
        assert result.returncode == 0
        assert "--output" in result.stdout
        assert "--batch" in result.stdout
        assert "--concurrent" in result.stdout

    def test_convert_help(self) -> None:
        result = self._run("convert")
        assert result.returncode == 0

    def test_gui_help(self) -> None:
        result = self._run("gui")
        assert result.returncode == 0
        assert "--theme" in result.stdout

    def test_auth_help(self) -> None:
        result = self._run("auth")
        assert result.returncode == 0
        assert "login" in result.stdout
        assert "logout" in result.stdout
        assert "status" in result.stdout

    def test_library_help(self) -> None:
        result = self._run("library")
        assert result.returncode != 0


class TestCLIImports:
    """验证所有模块能正常导入。"""

    def test_all_core_imports(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", """
from cnki_downloader.core.search import search
from cnki_downloader.core.downloader import download_paper, batch_download
from cnki_downloader.core.auth import login, logout, check_campus_network
from cnki_downloader.core.converter import convert_caj_to_pdf
from cnki_downloader.core.export import export_bibtex, export_endnote, export_gbt7714
from cnki_downloader.core.library import Category, Tag, build_category_tree
from cnki_downloader.core.session import SessionManager
from cnki_downloader.core.exceptions import CnkiError, install_global_handler
from cnki_downloader.db.database import Database
from cnki_downloader.db.repository import PaperRepository, TagRepository, CategoryRepository
from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult
from cnki_downloader.models.download_task import DownloadTask, TaskStatus
from cnki_downloader.services.search_service import SearchService
from cnki_downloader.services.download_service import DownloadService
from cnki_downloader.services.auth_service import AuthService
from cnki_downloader.utils.config import load_config
print("OK")
"""],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "OK" in result.stdout
