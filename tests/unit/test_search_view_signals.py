"""tests/unit/test_search_view_signals.py"""
import pytest

pytest.importorskip("PyQt6")

from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

from cnki_downloader.gui.views.search_view import SearchView


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _make_mock_vm():
    vm = MagicMock()
    vm.papers = []
    vm.is_loading = False
    return vm


def test_download_requested_signal_exists(qapp):
    """SearchView should have a download_requested signal."""
    view = SearchView(_make_mock_vm())
    assert hasattr(view, "download_requested")


def test_paper_double_clicked_signal_exists(qapp):
    """SearchView should have a paper_double_clicked signal."""
    view = SearchView(_make_mock_vm())
    assert hasattr(view, "paper_double_clicked")
