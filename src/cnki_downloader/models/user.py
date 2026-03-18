"""用户配置与凭证模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UserConfig:
    """用户配置"""

    download_dir: Path = field(default_factory=lambda: Path.home() / "Downloads" / "cnki")
    auto_convert_caj: bool = True
    max_concurrent_downloads: int = 3
    min_request_delay: float = 1.0
    max_request_delay: float = 3.0
    log_level: str = "INFO"


@dataclass
class Credential:
    """用户凭证"""

    username: str = ""
    password: str = ""
    auth_type: str = "campus"  # campus / account
