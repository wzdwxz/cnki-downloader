# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for CNKI Downloader (onedir mode)
#
# Usage: python scripts/build.py  (或 pyinstaller cnki_downloader.spec)
# Playwright 浏览器由 build.py post-build 阶段复制到 dist/ 目录

import importlib
import sys
from pathlib import Path

block_cipher = None

# ---------- 定位 Playwright driver 目录 ----------
playwright_datas = []
try:
    pw_pkg = importlib.import_module("playwright")
    pw_driver = Path(pw_pkg.__file__).parent / "driver"
    if pw_driver.is_dir():
        playwright_datas.append((str(pw_driver), "playwright/driver"))
except Exception:
    print("WARNING: playwright package not found, driver will not be bundled")

# ---------- Analysis ----------
a = Analysis(
    ['src/cnki_downloader/__main__.py'],
    pathex=[],
    binaries=[],
    datas=playwright_datas,
    hiddenimports=[
        # --- cnki_downloader 全部子模块 ---
        # core
        'cnki_downloader.core',
        'cnki_downloader.core.auth',
        'cnki_downloader.core.converter',
        'cnki_downloader.core.downloader',
        'cnki_downloader.core.exceptions',
        'cnki_downloader.core.export',
        'cnki_downloader.core.library',
        'cnki_downloader.core.search',
        'cnki_downloader.core.session',
        # models
        'cnki_downloader.models',
        'cnki_downloader.models.download_task',
        'cnki_downloader.models.paper',
        'cnki_downloader.models.search_result',
        'cnki_downloader.models.user',
        # db
        'cnki_downloader.db',
        'cnki_downloader.db.database',
        'cnki_downloader.db.repository',
        # services
        'cnki_downloader.services',
        'cnki_downloader.services.auth_service',
        'cnki_downloader.services.download_service',
        'cnki_downloader.services.library_service',
        'cnki_downloader.services.search_service',
        # utils
        'cnki_downloader.utils',
        'cnki_downloader.utils.config',
        'cnki_downloader.utils.crypto',
        'cnki_downloader.utils.frozen',
        'cnki_downloader.utils.logging',
        'cnki_downloader.utils.paths',
        # cli
        'cnki_downloader.cli',
        'cnki_downloader.cli.app',
        'cnki_downloader.cli.formatters',
        'cnki_downloader.cli.commands',
        'cnki_downloader.cli.commands.auth',
        'cnki_downloader.cli.commands.convert',
        'cnki_downloader.cli.commands.download',
        'cnki_downloader.cli.commands.library',
        'cnki_downloader.cli.commands.search',
        # gui
        'cnki_downloader.gui',
        'cnki_downloader.gui.app',
        'cnki_downloader.gui.main_window',
        'cnki_downloader.gui.themes',
        'cnki_downloader.gui.viewmodels',
        'cnki_downloader.gui.viewmodels.search_vm',
        'cnki_downloader.gui.viewmodels.download_vm',
        'cnki_downloader.gui.viewmodels.library_vm',
        'cnki_downloader.gui.views',
        'cnki_downloader.gui.views.search_view',
        'cnki_downloader.gui.views.download_view',
        'cnki_downloader.gui.views.library_view',
        'cnki_downloader.gui.views.login_dialog',
        'cnki_downloader.gui.views.settings_view',
        'cnki_downloader.gui.widgets',
        'cnki_downloader.gui.widgets.paper_card',
        'cnki_downloader.gui.widgets.progress_bar',
        'cnki_downloader.gui.widgets.tag_editor',
        'cnki_downloader.gui.workers',
        'cnki_downloader.gui.workers.browser_thread',
        'cnki_downloader.gui.workers.download_worker',
        'cnki_downloader.gui.workers.search_worker',
        # --- 第三方库 ---
        'aiosqlite',
        'h2',
        'hpack',
        'hyperframe',
        'keyring.backends',
        # playwright
        'playwright',
        'playwright.async_api',
        'playwright.sync_api',
        'playwright._impl',
        'playwright._impl._driver',
        # PyMuPDF
        'fitz',
        # lxml
        'lxml._elementpath',
        'lxml.etree',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        '_tkinter',
        'unittest',
        'pytest',
        'setuptools',
        'distutils',
        'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ---------- PYZ ----------
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------- EXE (onedir 模式: 不打包 binaries/datas 进 exe) ----------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='cnki_downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 关闭 UPX，避免损坏 Qt/Chromium DLL
    console=True,  # 保留控制台，CLI 和 GUI 共用入口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# ---------- COLLECT (onedir 输出) ----------
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='cnki_downloader',
)
