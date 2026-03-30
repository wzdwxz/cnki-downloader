"""MainWindow behavior tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from cnki_downloader.gui.main_window import MainWindow


def test_has_saved_cookies_returns_false_on_permission_error(monkeypatch, tmp_path) -> None:
    """Cookie probing should not crash GUI startup when the file is inaccessible."""
    cookie_file = tmp_path / "browser_state.json"

    monkeypatch.setattr(
        "cnki_downloader.utils.config.get_config_dir",
        lambda: tmp_path,
    )

    original_stat = Path.stat

    def fake_stat(self: Path, *args, **kwargs):
        if self == cookie_file:
            raise PermissionError("access denied")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)

    assert MainWindow._has_saved_cookies() is False
