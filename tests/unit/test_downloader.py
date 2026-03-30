"""Downloader module tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cnki_downloader.core.downloader import NullProgress, _sanitize_filename
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
