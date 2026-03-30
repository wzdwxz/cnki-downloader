"""API 自动探测模块单元测试"""

import json
import time
from pathlib import Path
from unittest.mock import patch

from cnki_downloader.core.api_probe import (
    _CACHE_TTL,
    get_current_endpoints,
    load_cached_endpoints,
    save_cached_endpoints,
)


class TestCacheEndpoints:
    def test_save_and_load(self, tmp_path) -> None:
        cache_file = tmp_path / "api_endpoints.json"

        with patch("cnki_downloader.core.api_probe._get_cache_file", return_value=cache_file):
            endpoints = {
                "version": "kns8s",
                "search_url": "https://kns.cnki.net/kns8s/defaultresult/index",
            }
            save_cached_endpoints(endpoints)

            loaded = load_cached_endpoints()
            assert loaded is not None
            assert loaded["version"] == "kns8s"
            assert loaded["search_url"] == "https://kns.cnki.net/kns8s/defaultresult/index"
            assert "probe_time" in loaded

    def test_load_returns_none_when_no_file(self, tmp_path) -> None:
        cache_file = tmp_path / "nonexistent.json"
        with patch("cnki_downloader.core.api_probe._get_cache_file", return_value=cache_file):
            assert load_cached_endpoints() is None

    def test_load_returns_none_on_permission_error(self, tmp_path, monkeypatch) -> None:
        cache_file = tmp_path / "api_endpoints.json"

        original_stat = Path.stat

        def fake_stat(self: Path, *args, **kwargs):
            if self == cache_file:
                raise PermissionError("access denied")
            return original_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", fake_stat)

        with patch("cnki_downloader.core.api_probe._get_cache_file", return_value=cache_file):
            assert load_cached_endpoints() is None

    def test_load_returns_none_when_expired(self, tmp_path) -> None:
        cache_file = tmp_path / "api_endpoints.json"
        expired_data = {
            "version": "kns8s",
            "search_url": "https://kns.cnki.net/kns8s/defaultresult/index",
            "probe_time": time.time() - _CACHE_TTL - 100,
        }
        cache_file.write_text(json.dumps(expired_data), encoding="utf-8")

        with patch("cnki_downloader.core.api_probe._get_cache_file", return_value=cache_file):
            assert load_cached_endpoints() is None

    def test_load_returns_data_when_fresh(self, tmp_path) -> None:
        cache_file = tmp_path / "api_endpoints.json"
        fresh_data = {
            "version": "kns8s",
            "search_url": "https://kns.cnki.net/kns8s/defaultresult/index",
            "probe_time": time.time() - 100,
        }
        cache_file.write_text(json.dumps(fresh_data), encoding="utf-8")

        with patch("cnki_downloader.core.api_probe._get_cache_file", return_value=cache_file):
            loaded = load_cached_endpoints()
            assert loaded is not None
            assert loaded["version"] == "kns8s"


class TestGetCurrentEndpoints:
    def test_returns_default_when_no_cache(self) -> None:
        with patch("cnki_downloader.core.api_probe.load_cached_endpoints", return_value=None):
            endpoints = get_current_endpoints()
            assert endpoints["version"] == "kns8s"
            assert "defaultresult/index" in endpoints["search_url"]

    def test_returns_cached_when_available(self) -> None:
        cached = {
            "version": "kns9",
            "search_url": "https://kns.cnki.net/kns9/defaultresult/index",
        }
        with patch("cnki_downloader.core.api_probe.load_cached_endpoints", return_value=cached):
            endpoints = get_current_endpoints()
            assert endpoints["version"] == "kns9"
