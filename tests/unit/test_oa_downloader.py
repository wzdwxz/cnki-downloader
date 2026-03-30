"""Open-access downloader tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from cnki_downloader.core.exceptions import DownloadError
from cnki_downloader.core.oa_downloader import (
    OpenAccessResult,
    download_open_access_pdf,
    resolve_open_access_pdf,
)


@pytest.mark.asyncio
async def test_resolve_prefers_unpaywall(monkeypatch) -> None:
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_unpaywall",
        AsyncMock(
            return_value=OpenAccessResult(
                provider="unpaywall",
                pdf_url="https://example.com/a.pdf",
                doi="10.1000/a",
                title="A",
            )
        ),
    )
    crossref = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_crossref_pdf_by_doi",
        crossref,
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_europepmc_pdf_by_doi",
        AsyncMock(return_value=None),
    )

    result = await resolve_open_access_pdf(doi="10.1000/a", client=object())
    assert result.provider == "unpaywall"
    assert crossref.await_count == 0


@pytest.mark.asyncio
async def test_resolve_falls_back_to_crossref(monkeypatch) -> None:
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_unpaywall",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_crossref_pdf_by_doi",
        AsyncMock(
            return_value=OpenAccessResult(
                provider="crossref",
                pdf_url="https://example.com/b.pdf",
                doi="10.1000/b",
                title="B",
            )
        ),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_europepmc_pdf_by_doi",
        AsyncMock(return_value=None),
    )

    result = await resolve_open_access_pdf(doi="10.1000/b", client=object())
    assert result.provider == "crossref"


@pytest.mark.asyncio
async def test_resolve_uses_title_to_find_doi(monkeypatch) -> None:
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_doi_by_title_crossref",
        AsyncMock(return_value={"doi": "10.1000/title", "title": "Title Hit"}),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_unpaywall",
        AsyncMock(
            return_value=OpenAccessResult(
                provider="unpaywall",
                pdf_url="https://example.com/t.pdf",
                doi="10.1000/title",
                title="Title Hit",
            )
        ),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_crossref_pdf_by_doi",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_europepmc_pdf_by_doi",
        AsyncMock(return_value=None),
    )

    result = await resolve_open_access_pdf(title="Some title", client=object())
    assert result.doi == "10.1000/title"


@pytest.mark.asyncio
async def test_resolve_raises_when_no_provider_hit(monkeypatch) -> None:
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_doi_by_title_crossref",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_unpaywall",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_crossref_pdf_by_doi",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_europepmc_pdf_by_doi",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "cnki_downloader.core.oa_downloader._lookup_arxiv_pdf_by_title",
        AsyncMock(return_value=None),
    )

    with pytest.raises(DownloadError, match="No open-access PDF source found"):
        await resolve_open_access_pdf(title="Not Found", client=object())


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content: bytes = b"",
        content_type: str = "application/pdf",
        path: str = "/paper.pdf",
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}
        self.url = type("URL", (), {"path": path})()

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise DownloadError(f"http {self.status_code}")


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def get(self, url: str, **kwargs):
        return self._response


@pytest.mark.asyncio
async def test_download_open_access_pdf_writes_file(tmp_path) -> None:
    result = OpenAccessResult(
        provider="unpaywall",
        pdf_url="https://example.com/paper.pdf",
        doi="10.1000/x",
        title="Paper X",
    )
    client = _FakeClient(_FakeResponse(content=b"%PDF-1.6\ncontent"))

    path = await download_open_access_pdf(result, tmp_path, client=client)
    assert path.exists()
    assert path.suffix == ".pdf"
    assert path.read_bytes().startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_download_open_access_pdf_rejects_non_pdf(tmp_path) -> None:
    result = OpenAccessResult(
        provider="crossref",
        pdf_url="https://example.com/page",
        title="Not PDF",
    )
    client = _FakeClient(
        _FakeResponse(
            content=b"<html>not pdf</html>",
            content_type="text/html",
            path="/page",
        )
    )

    with pytest.raises(DownloadError, match="did not return PDF"):
        await download_open_access_pdf(result, tmp_path, client=client)
