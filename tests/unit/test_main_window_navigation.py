"""MainWindow navigation tests."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from cnki_downloader.gui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_main_window_hides_library_navigation(qapp) -> None:
    window = MainWindow()
    button_texts = [button.text() for button in window._nav_buttons]

    assert "文献库" not in button_texts
    assert button_texts == ["搜索文献", "下载管理", "设置"]
