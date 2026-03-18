"""配置模块单元测试"""

from pathlib import Path

from cnki_downloader.models.user import UserConfig
from cnki_downloader.utils.config import get_config_dir, get_data_dir


class TestUserConfig:
    def test_defaults(self) -> None:
        config = UserConfig()
        assert config.download_dir == Path.home() / "Downloads" / "cnki"
        assert config.auto_convert_caj is True
        assert config.max_concurrent_downloads == 3
        assert config.log_level == "INFO"


class TestConfigDirs:
    def test_config_dir_exists(self) -> None:
        d = get_config_dir()
        assert d.exists()

    def test_data_dir_exists(self) -> None:
        d = get_data_dir()
        assert d.exists()
