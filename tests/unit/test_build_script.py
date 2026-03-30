"""Tests for the build script helpers."""

from __future__ import annotations

import importlib
from pathlib import Path


def test_pre_build_reuses_existing_browser_install(monkeypatch, tmp_path) -> None:
    build = importlib.import_module("scripts.build")

    browsers_dir = tmp_path / "ms-playwright"
    chromium_dir = browsers_dir / "chromium-1234"
    chromium_dir.mkdir(parents=True)

    monkeypatch.setattr(build, "_find_playwright_browsers", lambda: browsers_dir)
    monkeypatch.setattr(build, "_run", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("playwright install should not run when Chromium already exists")
    ))

    assert build.pre_build() == (browsers_dir, chromium_dir.name)


def test_find_playwright_browsers_skips_inaccessible_candidates(monkeypatch, tmp_path) -> None:
    build = importlib.import_module("scripts.build")

    blocked_root = tmp_path / "localappdata"
    blocked = blocked_root / "ms-playwright"
    allowed_home = tmp_path / "home"
    allowed = allowed_home / "AppData" / "Local" / "ms-playwright"
    allowed.mkdir(parents=True)
    (allowed / "chromium-1234").mkdir()

    original_is_dir = Path.is_dir
    original_iterdir = Path.iterdir

    monkeypatch.setattr(build.platform, "system", lambda: "Windows")
    monkeypatch.setattr(build.os, "environ", {"LOCALAPPDATA": str(blocked_root)})
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: allowed_home))

    def fake_is_dir(self: Path) -> bool:
        if self in {blocked, allowed}:
            return True
        return original_is_dir(self)

    def fake_iterdir(self: Path):
        if self == blocked:
            raise PermissionError("access denied")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "is_dir", fake_is_dir)
    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    assert build._find_playwright_browsers() == allowed


def test_pre_build_installs_chromium_into_project_local_cache(monkeypatch, tmp_path) -> None:
    build = importlib.import_module("scripts.build")

    local_cache = tmp_path / ".playwright-browsers"
    chromium_dir = local_cache / "chromium-1234"
    state = {"calls": 0}

    monkeypatch.setattr(build, "PLAYWRIGHT_CACHE_DIR", local_cache)

    def fake_find():
        state["calls"] += 1
        if state["calls"] == 1:
            return None
        chromium_dir.mkdir(parents=True, exist_ok=True)
        return local_cache

    def fake_run(cmd, **kwargs):
        assert kwargs["env"]["PLAYWRIGHT_BROWSERS_PATH"] == str(local_cache)

    monkeypatch.setattr(build, "_find_playwright_browsers", fake_find)
    monkeypatch.setattr(build, "_run", fake_run)

    assert build.pre_build() == (local_cache, chromium_dir.name)


def test_smoke_test_executable_uses_help_command(monkeypatch, tmp_path) -> None:
    build = importlib.import_module("scripts.build")

    exe_path = tmp_path / "cnki_downloader.exe"
    exe_path.write_text("", encoding="utf-8")
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["kwargs"] = kwargs

    monkeypatch.setattr(build, "_run", fake_run)

    build._smoke_test_executable(exe_path)

    assert calls["cmd"] == [str(exe_path), "--help"]


def test_post_build_copies_matching_headless_shell(monkeypatch, tmp_path) -> None:
    build = importlib.import_module("scripts.build")

    browsers_dir = tmp_path / "ms-playwright"
    chromium_dir = browsers_dir / "chromium-1234"
    headless_shell_dir = browsers_dir / "chromium_headless_shell-1234"
    (chromium_dir / "chrome-win64").mkdir(parents=True)
    (chromium_dir / "chrome-win64" / "chrome.exe").write_text("", encoding="utf-8")
    (headless_shell_dir / "chrome-headless-shell-win64").mkdir(parents=True)
    (headless_shell_dir / "chrome-headless-shell-win64" / "chrome-headless-shell.exe").write_text(
        "",
        encoding="utf-8",
    )

    dist_dir = tmp_path / "dist" / "cnki_downloader"
    (dist_dir / "playwright" / "driver").mkdir(parents=True)
    (dist_dir / "cnki_downloader.exe").write_text("", encoding="utf-8")

    monkeypatch.setattr(build, "DIST_DIR", dist_dir)
    monkeypatch.setattr(build, "_dir_size_mb", lambda path: 0.0)
    monkeypatch.setattr(build, "_smoke_test_executable", lambda path: None)

    build.post_build(browsers_dir, chromium_dir.name)

    assert (dist_dir / "playwright" / "browsers" / "chromium-1234").is_dir()
    assert (dist_dir / "playwright" / "browsers" / "chromium_headless_shell-1234").is_dir()
