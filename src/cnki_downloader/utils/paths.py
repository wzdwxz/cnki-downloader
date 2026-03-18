"""跨平台路径管理"""

from __future__ import annotations

from pathlib import Path

from cnki_downloader.utils.config import get_data_dir


def get_db_path() -> Path:
    """获取SQLite数据库文件路径。"""
    return get_data_dir() / "cnki_downloader.db"


def get_default_download_dir() -> Path:
    """获取默认下载目录。"""
    download_dir = Path.home() / "Downloads" / "cnki"
    download_dir.mkdir(parents=True, exist_ok=True)
    return download_dir
