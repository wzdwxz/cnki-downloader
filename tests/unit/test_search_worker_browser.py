"""tests/unit/test_search_worker_browser.py"""
import pytest


def test_no_module_level_browser_globals():
    """Module should not have mutable browser globals."""
    import cnki_downloader.gui.workers.search_worker as mod

    assert not hasattr(mod, "_browser"), "_browser global should be removed"
    assert not hasattr(mod, "_context"), "_context global should be removed"
    assert not hasattr(mod, "_page"), "_page global should be removed"


def test_no_get_page_function():
    """Module should not have the _get_page helper."""
    import cnki_downloader.gui.workers.search_worker as mod

    assert not hasattr(mod, "_get_page"), "_get_page function should be removed"


def test_no_close_browser_function():
    """Module should not have the close_browser helper."""
    import cnki_downloader.gui.workers.search_worker as mod

    assert not hasattr(mod, "close_browser"), "close_browser function should be removed"


@pytest.mark.asyncio
async def test_verify_page_in_headless_search_fails_fast():
    from cnki_downloader.core.exceptions import CaptchaRequiredError
    from cnki_downloader.gui.workers.search_worker import SearchWorker
    from cnki_downloader.models.search_result import SearchQuery

    class FakePage:
        def __init__(self) -> None:
            self.url = "https://kns.cnki.net/verify"
            self.wait_for_url_calls = 0

        async def goto(self, url: str, timeout: int) -> None:
            return None

        async def wait_for_selector(self, selector: str, timeout: int) -> None:
            return None

        async def wait_for_url(self, predicate, timeout: int) -> None:
            self.wait_for_url_calls += 1
            raise TimeoutError("hidden browser cannot complete captcha")

    worker = SearchWorker(
        query=SearchQuery(keyword="test"),
        browser_thread=object(),
    )
    page = FakePage()

    with pytest.raises(CaptchaRequiredError):
        await worker._do_search(page, worker._query)

    assert page.wait_for_url_calls == 0


@pytest.mark.asyncio
async def test_search_reports_browser_startup_error_instead_of_install_hint():
    from cnki_downloader.gui.workers.search_worker import SearchWorker
    from cnki_downloader.models.search_result import SearchQuery

    class FakeBrowserThread:
        async def get_page(self):
            raise RuntimeError("Executable doesn't exist at bundled path")

    worker = SearchWorker(
        query=SearchQuery(keyword="test"),
        browser_thread=FakeBrowserThread(),
    )

    with pytest.raises(RuntimeError, match="bundled path"):
        await worker._search()
