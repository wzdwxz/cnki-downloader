"""三阶段构建脚本 — Pre-build / Build / Post-build

将 cnki_downloader 打包为 onedir 独立可执行文件，并捆绑 Chromium 浏览器。
"""

from __future__ import annotations

import io
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# 修复 Windows 控制台 GBK 编码问题
if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = PROJECT_ROOT / "cnki_downloader.spec"
DIST_DIR = PROJECT_ROOT / "dist" / "cnki_downloader"
PLAYWRIGHT_CACHE_DIR = PROJECT_ROOT / ".playwright-browsers"


# ──────────────────── 工具函数 ────────────────────

def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  → {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def _dir_size_mb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / (1024 * 1024)


def _playwright_install_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_CACHE_DIR)
    return env


def _smoke_test_executable(exe_path: Path) -> None:
    """执行最小 CLI 冒烟测试，确认产物至少能启动并输出帮助。"""
    print("\n  Smoke testing executable...")
    _run(
        [str(exe_path), "--help"],
        cwd=str(exe_path.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _find_playwright_browsers() -> Path | None:
    """定位 Playwright 安装的浏览器目录。

    优先使用 PLAYWRIGHT_BROWSERS_PATH 环境变量，否则使用默认路径。
    """
    env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            return p

    if platform.system() == "Windows":
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright",
            Path.home() / "AppData" / "Local" / "ms-playwright",
        ]
    elif platform.system() == "Darwin":
        candidates = [
            Path.home() / "Library" / "Caches" / "ms-playwright",
        ]
    else:
        candidates = [
            Path.home() / ".cache" / "ms-playwright",
        ]

    for p in candidates:
        try:
            if p.is_dir() and any(p.iterdir()):
                return p
        except OSError:
            continue

    return None


def _find_chromium_dirs(browsers_dir: Path) -> list[Path]:
    """返回可用的 Chromium 浏览器目录列表。"""
    return sorted(
        d for d in browsers_dir.glob("chromium-*") if d.is_dir()
    )


def _related_browser_dirs(browsers_dir: Path, chromium_name: str) -> list[Path]:
    """返回打包所需的 Chromium 相关目录。

    Playwright 在 headless 模式下会优先寻找与 Chromium 同 revision 的
    chromium_headless_shell 目录，所以发布包需要一并复制。
    """
    related = [browsers_dir / chromium_name]

    revision = chromium_name.removeprefix("chromium-")
    headless_shell = browsers_dir / f"chromium_headless_shell-{revision}"
    if headless_shell.is_dir():
        related.append(headless_shell)

    return related


# ──────────────────── Phase 1: Pre-build ────────────────────

def pre_build() -> Path:
    """检查依赖并安装 Chromium，返回浏览器目录路径。"""
    print("\n=== Phase 1: Pre-build ===\n")

    # 检查关键依赖
    missing = []
    for mod_name, pkg_hint in [
        ("playwright", "playwright"),
        ("PyQt6", "PyQt6"),
        ("fitz", "PyMuPDF"),
    ]:
        try:
            __import__(mod_name)
            print(f"  ✓ {mod_name}")
        except ImportError:
            missing.append(f"{mod_name} (pip install {pkg_hint})")
            print(f"  ✗ {mod_name}")

    if missing:
        print(f"\nError: missing dependencies: {', '.join(missing)}")
        print("Run:  pip install -e \".[all]\"")
        sys.exit(1)

    # 定位浏览器目录
    browsers_dir = _find_playwright_browsers()
    chromium_dirs: list[Path] = []
    if browsers_dir is not None:
        chromium_dirs = _find_chromium_dirs(browsers_dir)

    if not chromium_dirs:
        print("\n  Installing Chromium via Playwright...")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_CACHE_DIR)
        _run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            env=_playwright_install_env(),
        )
        browsers_dir = _find_playwright_browsers()
        if browsers_dir is not None:
            chromium_dirs = _find_chromium_dirs(browsers_dir)

    if browsers_dir is None:
        print("Error: cannot locate Playwright browsers directory")
        sys.exit(1)

    print(f"  Playwright browsers: {browsers_dir}")

    if not chromium_dirs:
        print(f"Error: no chromium directory found in {browsers_dir}")
        sys.exit(1)

    # 只保留最新版本的路径
    latest_chromium = chromium_dirs[-1]
    print(f"  Found: {latest_chromium.name}")
    return browsers_dir, latest_chromium.name


# ──────────────────── Phase 2: Build ────────────────────

def build() -> None:
    """运行 PyInstaller。"""
    print("\n=== Phase 2: PyInstaller Build ===\n")

    if not SPEC_FILE.exists():
        print(f"Error: spec file not found: {SPEC_FILE}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(SPEC_FILE),
        "--distpath", str(PROJECT_ROOT / "dist"),
        "--workpath", str(PROJECT_ROOT / "build"),
        "--clean",
        "--noconfirm",
    ]
    _run(cmd, cwd=str(PROJECT_ROOT))

    if not DIST_DIR.is_dir():
        print(f"Error: expected output directory not found: {DIST_DIR}")
        sys.exit(1)

    print(f"\n  PyInstaller output: {DIST_DIR}")


# ──────────────────── Phase 3: Post-build ────────────────────

def post_build(browsers_dir: Path, chromium_name: str) -> None:
    """复制 Chromium 浏览器到 dist 目录并验证。

    复制当前 Playwright revision 对应的 Chromium 运行时目录。
    """
    print("\n=== Phase 3: Post-build ===\n")

    dest_browsers = DIST_DIR / "playwright" / "browsers"
    dest_browsers.mkdir(parents=True, exist_ok=True)

    # 同时复制完整 Chromium 和对应的 headless shell。
    for src in _related_browser_dirs(browsers_dir, chromium_name):
        dest = dest_browsers / src.name
        if dest.exists():
            shutil.rmtree(dest)
        print(f"  Copying {src.name} ...")
        shutil.copytree(src, dest)

    # 复制 Playwright driver（如果 PyInstaller 未打包）
    dest_driver = DIST_DIR / "playwright" / "driver"
    if not dest_driver.is_dir():
        try:
            import playwright as pw_mod
            src_driver = Path(pw_mod.__file__).parent / "driver"
            if src_driver.is_dir():
                print("  Copying playwright driver ...")
                shutil.copytree(src_driver, dest_driver)
        except ImportError:
            pass

    # ── 验证关键文件 ──
    print("\n  Verifying key files...")
    checks = {
        "executable": DIST_DIR / "cnki_downloader.exe",
        "playwright driver": DIST_DIR / "playwright" / "driver",
        "chromium browsers": dest_browsers,
    }
    all_ok = True
    for label, path in checks.items():
        if path.exists():
            print(f"  ✓ {label}: {path.relative_to(DIST_DIR)}")
        else:
            print(f"  ✗ {label}: MISSING ({path})")
            all_ok = False

    # 检查 chromium 可执行文件
    chrome_exe_candidates = list(dest_browsers.rglob("chrome.exe"))
    if not chrome_exe_candidates:
        chrome_exe_candidates = list(dest_browsers.rglob("chromium"))
    if chrome_exe_candidates:
        print(f"  ✓ chrome executable: {chrome_exe_candidates[0].relative_to(DIST_DIR)}")
    else:
        print("  ✗ chrome executable: NOT FOUND")
        all_ok = False

    headless_shell_candidates = list(dest_browsers.rglob("chrome-headless-shell.exe"))
    if headless_shell_candidates:
        print(
            "  ✓ headless shell: "
            f"{headless_shell_candidates[0].relative_to(DIST_DIR)}"
        )
    else:
        print("  ✗ headless shell: NOT FOUND")
        all_ok = False

    if not all_ok:
        print("\nWarning: some files are missing, the build may not work correctly")
    else:
        _smoke_test_executable(checks["executable"])

    # ── 输出大小 ──
    total_mb = _dir_size_mb(DIST_DIR)
    print(f"\n  Total size: {total_mb:.1f} MB")
    print(f"  Output: {DIST_DIR}")


# ──────────────────── Main ────────────────────

def main() -> None:
    print("=" * 60)
    print("  CNKI Downloader — Build (onedir + Chromium)")
    print("=" * 60)

    browsers_dir, chromium_name = pre_build()
    build()
    post_build(browsers_dir, chromium_name)

    print("\n" + "=" * 60)
    print("  Build complete!")
    print(f"  Run: {DIST_DIR / 'cnki_downloader.exe'} gui")
    print("=" * 60)


if __name__ == "__main__":
    main()
