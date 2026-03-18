"""配置加载 — 环境变量 + TOML配置文件"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cnki_downloader.models.user import UserConfig

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def get_config_dir() -> Path:
    """获取配置目录（跨平台）。"""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    config_dir = base / "cnki_downloader"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    """获取数据目录（数据库等）。"""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    data_dir = base / "cnki_downloader"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def load_config() -> UserConfig:
    """加载用户配置。优先级：环境变量 > 配置文件 > 默认值。"""
    config = UserConfig()

    # 尝试从TOML配置文件加载
    config_file = get_config_dir() / "config.toml"
    if config_file.exists():
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
        if "download_dir" in data:
            config.download_dir = Path(data["download_dir"])
        if "auto_convert_caj" in data:
            config.auto_convert_caj = data["auto_convert_caj"]
        if "max_concurrent_downloads" in data:
            config.max_concurrent_downloads = data["max_concurrent_downloads"]
        if "log_level" in data:
            config.log_level = data["log_level"]

    # 环境变量覆盖
    if env_dir := os.environ.get("CNKI_DOWNLOAD_DIR"):
        config.download_dir = Path(env_dir)
    if env_log := os.environ.get("CNKI_LOG_LEVEL"):
        config.log_level = env_log

    return config
