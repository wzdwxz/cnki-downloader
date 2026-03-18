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
