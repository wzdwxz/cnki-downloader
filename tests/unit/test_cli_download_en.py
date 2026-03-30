"""CLI download-en command tests."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import typer

from cnki_downloader.core.oa_downloader import OpenAccessResult


@pytest.mark.asyncio
async def test_download_en_async_uses_doi_when_query_is_doi(monkeypatch, tmp_path) -> None:
    from cnki_downloader.cli.commands import download_en as mod

    resolve_mock = AsyncMock(
        return_value=OpenAccessResult(
            provider="unpaywall",
            pdf_url="https://example.com/paper.pdf",
            doi="10.1000/test",
            title="Sample",
        )
    )
    download_mock = AsyncMock(return_value=tmp_path / "sample.pdf")

    monkeypatch.setattr(mod, "resolve_open_access_pdf", resolve_mock)
    monkeypatch.setattr(mod, "download_open_access_pdf", download_mock)
    monkeypatch.setattr(mod.console, "status", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(mod.console, "print", lambda *args, **kwargs: None)

    result_path = await mod._download_en_async(
        query="10.1000/test",
        output_dir=tmp_path,
        filename="",
        email="",
    )

    assert result_path == Path(tmp_path / "sample.pdf")
    kwargs = resolve_mock.await_args.kwargs
    assert kwargs["doi"] == "10.1000/test"
    assert kwargs["title"] == ""


@pytest.mark.asyncio
async def test_download_en_async_uses_title_when_not_doi(monkeypatch, tmp_path) -> None:
    from cnki_downloader.cli.commands import download_en as mod

    resolve_mock = AsyncMock(
        return_value=OpenAccessResult(
            provider="arxiv",
            pdf_url="https://arxiv.org/pdf/1234.5678.pdf",
            title="Test title",
        )
    )

    monkeypatch.setattr(mod, "resolve_open_access_pdf", resolve_mock)
    monkeypatch.setattr(
        mod,
        "download_open_access_pdf",
        AsyncMock(return_value=tmp_path / "test_title.pdf"),
    )
    monkeypatch.setattr(mod.console, "status", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(mod.console, "print", lambda *args, **kwargs: None)

    await mod._download_en_async(
        query="A non DOI title",
        output_dir=tmp_path,
        filename="",
        email="",
    )

    kwargs = resolve_mock.await_args.kwargs
    assert kwargs["doi"] == ""
    assert kwargs["title"] == "A non DOI title"


def test_download_en_command_exits_cleanly_on_error(monkeypatch, tmp_path) -> None:
    from cnki_downloader.cli.commands import download_en as mod

    monkeypatch.setattr(
        mod,
        "_download_en_async",
        AsyncMock(side_effect=RuntimeError("timeout")),
    )
    monkeypatch.setattr(mod.console, "print", lambda *args, **kwargs: None)

    with pytest.raises(typer.Exit):
        mod.download_en_command(
            query="test title",
            output=tmp_path,
            filename="",
            email="",
        )
