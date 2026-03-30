"""PyInstaller 冻结模式检测与 Playwright 路径设置"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """检测是否在 PyInstaller 打包环境中运行。"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_bundle_dir() -> Path:
    """获取打包后的应用根目录（onedir 模式下为 exe 所在目录）。"""
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[3]  # 开发时: src/../../../


def setup_playwright_env() -> None:
    """在 Playwright 导入前设置环境变量，使其使用打包内的浏览器和驱动。

    仅在 PyInstaller 冻结模式下生效。开发模式下什么都不做。
    """
    if not is_frozen():
        return

    bundle = get_bundle_dir()

    # Playwright 浏览器路径 → dist/cnki_downloader/playwright/browsers/
    browsers_path = bundle / "playwright" / "browsers"
    if browsers_path.is_dir():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)

    # Playwright Node.js 驱动路径 → dist/cnki_downloader/playwright/driver/
    driver_dir = bundle / "playwright" / "driver"
    if driver_dir.is_dir():
        # Windows: node.exe
        node_exe = driver_dir / "node.exe"
        if node_exe.is_file():
            os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(node_exe)
