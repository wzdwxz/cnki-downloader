"""MCP server unit tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cnki_downloader.mcp_server import mcp


def test_mcp_server_has_all_tools() -> None:
    tool_names = {t.name for t in mcp._tool_manager.list_tools()}
    expected = {
        "cnki_search",
        "cnki_download",
        "cnki_download_en",
        "cnki_convert",
        "cnki_auth_status",
        "cnki_auth_login",
    }
    assert expected == tool_names


def test_mcp_server_name() -> None:
    assert mcp.name == "cnki"


def test_cnki_convert_tool_with_nonexistent_file() -> None:
    from cnki_downloader.mcp_server import cnki_convert

    result = cnki_convert(file_path="/nonexistent/file.caj")
    assert result["error"] == "convert_error"


def test_cnki_auth_status_returns_dict() -> None:
    from cnki_downloader.mcp_server import cnki_auth_status

    result = cnki_auth_status()
    assert "authenticated" in result
    assert "cookie_count" in result
    assert "state_file" in result


@pytest.mark.asyncio
async def test_cnki_download_en_requires_input() -> None:
    from cnki_downloader.mcp_server import cnki_download_en

    result = await cnki_download_en()
    assert result["error"] == "invalid_params"


@pytest.mark.asyncio
async def test_cnki_download_en_success(monkeypatch, tmp_path) -> None:
    from cnki_downloader.core.oa_downloader import OpenAccessResult
    from cnki_downloader.mcp_server import cnki_download_en

    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader.resolve_open_access_pdf",
        AsyncMock(
            return_value=OpenAccessResult(
                provider="unpaywall",
                pdf_url="https://example.com/paper.pdf",
                doi="10.1000/test",
                title="Sample Paper",
            )
        ),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader.download_open_access_pdf",
        AsyncMock(return_value=tmp_path / "sample.pdf"),
    )

    result = await cnki_download_en(doi="10.1000/test", output_dir=str(tmp_path))
    assert result["success"] is True
    assert result["provider"] == "unpaywall"
    assert result["file_path"] == str(Path(tmp_path / "sample.pdf"))
