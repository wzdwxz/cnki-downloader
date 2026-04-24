"""Downloader module tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cnki_downloader.core.downloader import (
    NullProgress,
    _sanitize_filename,
    build_filename,
    paper_from_url,
)
from cnki_downloader.core.exceptions import DownloadError
from cnki_downloader.models.paper import Paper


class TestSanitizeFilename:
    def test_normal(self) -> None:
        assert _sanitize_filename("normal title") == "normal title"

    def test_special_chars(self) -> None:
        result = _sanitize_filename('file<name>:bad\\chars|test?*')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_max_length(self) -> None:
        long_name = "a" * 200
        result = _sanitize_filename(long_name, max_length=50)
        assert len(result) == 50

    def test_empty(self) -> None:
        assert _sanitize_filename("") == "untitled"


class TestBuildFilename:
    def test_author_year_three_words(self) -> None:
        paper = Paper(
            title="A Study of Deep Learning Models",
            authors=["Zhang San", "Li Si"],
            publish_date="2023-05-01",
        )
        assert build_filename(paper) == "Zhang San(2023) A Study of"

    def test_chinese_title_no_whitespace(self) -> None:
        paper = Paper(
            title="基于深度学习的图像识别方法研究",
            authors=["张三"],
            publish_date="2024",
        )
        # 中文标题无空白时整体保留，交给 max_length 截断
        assert build_filename(paper) == "张三(2024) 基于深度学习的图像识别方法研究"

    def test_missing_author_uses_year_and_title(self) -> None:
        paper = Paper(title="Hello World Study", publish_date="2020-01")
        assert build_filename(paper) == "(2020) Hello World Study"

    def test_missing_year_uses_author_and_title(self) -> None:
        paper = Paper(title="Hello World Study", authors=["Alice"])
        assert build_filename(paper) == "Alice Hello World Study"

    def test_only_title(self) -> None:
        paper = Paper(title="One Two Three Four Five")
        assert build_filename(paper) == "One Two Three"

    def test_empty_paper_falls_back_to_cnki_id(self) -> None:
        paper = Paper(title="", dbname="CJFDLAST", filename="ABC123")
        assert build_filename(paper) == "CJFDLAST_ABC123"

    def test_empty_everything_returns_untitled(self) -> None:
        assert build_filename(Paper(title="")) == "untitled"

    def test_respects_max_length(self) -> None:
        paper = Paper(title="x" * 500, authors=["A"], publish_date="2024")
        result = build_filename(paper, max_length=40)
        assert len(result) == 40

    def test_sanitizes_illegal_chars(self) -> None:
        paper = Paper(title="a/b:c", authors=["x|y"], publish_date="2024")
        result = build_filename(paper)
        for ch in '<>:"/\\|?*':
            assert ch not in result

    def test_batch_produces_distinct_names(self) -> None:
        papers = [
            Paper(title="First Paper About Things", authors=["Alice"], publish_date="2023"),
            Paper(title="Second Paper About Things", authors=["Bob"], publish_date="2024"),
            Paper(title="Third Paper About Things", authors=["Carol"], publish_date="2025"),
        ]
        names = {build_filename(p) for p in papers}
        assert len(names) == 3


class TestPaperFromUrl:
    def test_extracts_dbname_and_filename(self) -> None:
        url = (
            "https://kns.cnki.net/kcms/detail/detail.aspx"
            "?dbcode=CJFD&dbname=CJFDLAST&filename=ABC123"
        )
        paper = paper_from_url(url)
        assert paper.dbname == "CJFDLAST"
        assert paper.filename == "ABC123"
        assert paper.url == url

    def test_falls_back_to_download_without_params(self) -> None:
        paper = paper_from_url("https://example.com/foo")
        assert paper.title == "download"
        assert paper.dbname == ""
        assert paper.filename == ""


class TestNullProgress:
    def test_no_error(self) -> None:
        p = NullProgress()
        p.on_progress("t1", 100, 1000)
        p.on_complete("t1", Path("."))
        p.on_error("t1", Exception("test"))


@pytest.mark.asyncio
async def test_download_paper_falls_back_when_head_fails(monkeypatch, tmp_path) -> None:
    from cnki_downloader.core import downloader as downloader_mod

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/pdf", "content-length": "4"}

        async def aiter_bytes(self, chunk_size: int = 8192):
            yield b"test"

        async def aclose(self) -> None:
            return None

    class FakeSession:
        async def head(self, url: str, **kwargs):
            raise RuntimeError("head failed")

        async def stream_download(self, url: str, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        downloader_mod,
        "get_download_url",
        AsyncMock(return_value="https://example.com/file.pdf"),
    )

    paper = Paper(title="demo", url="https://example.com/detail")
    output = await downloader_mod.download_paper(FakeSession(), paper, tmp_path)

    assert output.exists()
    assert output.suffix == ".pdf"
    assert output.read_bytes() == b"test"


@pytest.mark.asyncio
async def test_download_paper_raises_on_redirect_stream(monkeypatch, tmp_path) -> None:
    from cnki_downloader.core import downloader as downloader_mod

    class FakeResponse:
        status_code = 302
        headers = {"location": "https://example.com/login"}

        async def aiter_bytes(self, chunk_size: int = 8192):
            raise AssertionError("aiter_bytes() should not be called for redirects")

        async def aclose(self) -> None:
            return None

    class FakeSession:
        async def head(self, url: str, **kwargs):
            raise RuntimeError("head failed")

        async def stream_download(self, url: str, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        downloader_mod,
        "get_download_url",
        AsyncMock(return_value="https://example.com/file.pdf"),
    )

    paper = Paper(title="demo", url="https://example.com/detail")
    with pytest.raises(DownloadError, match="redirected unexpectedly"):
        await downloader_mod.download_paper(FakeSession(), paper, tmp_path)
