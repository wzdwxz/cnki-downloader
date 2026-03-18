# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for CNKI Downloader

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['src/cnki_downloader/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'cnki_downloader.gui',
        'cnki_downloader.gui.app',
        'cnki_downloader.gui.main_window',
        'cnki_downloader.gui.views.search_view',
        'cnki_downloader.gui.views.download_view',
        'cnki_downloader.gui.views.library_view',
        'cnki_downloader.gui.views.login_dialog',
        'cnki_downloader.gui.views.settings_view',
        'cnki_downloader.gui.viewmodels.search_vm',
        'cnki_downloader.gui.viewmodels.download_vm',
        'cnki_downloader.gui.viewmodels.library_vm',
        'cnki_downloader.gui.workers.search_worker',
        'cnki_downloader.gui.workers.download_worker',
        'cnki_downloader.gui.widgets.paper_card',
        'cnki_downloader.gui.widgets.progress_bar',
        'cnki_downloader.gui.themes',
        'cnki_downloader.core.search',
        'cnki_downloader.core.downloader',
        'cnki_downloader.core.auth',
        'cnki_downloader.core.converter',
        'cnki_downloader.core.export',
        'cnki_downloader.core.library',
        'cnki_downloader.core.session',
        'cnki_downloader.db.database',
        'cnki_downloader.db.repository',
        'cnki_downloader.services',
        'aiosqlite',
        'h2',
        'hpack',
        'hyperframe',
        'keyring.backends',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='cnki_downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI模式，不显示控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可替换为实际图标路径
)
