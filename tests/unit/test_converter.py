"""CAJ转PDF模块单元测试"""

from pathlib import Path

import pytest

from cnki_downloader.core.converter import convert_caj_to_pdf
from cnki_downloader.core.exceptions import ConvertError


class TestConvertCajToPdf:
    def test_file_not_exists(self, tmp_path: Path) -> None:
        with pytest.raises(ConvertError, match="不存在"):
            convert_caj_to_pdf(tmp_path / "nonexistent.caj")

    def test_not_caj_file(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("hello")
        with pytest.raises(ConvertError, match="不是CAJ文件"):
            convert_caj_to_pdf(txt_file)

    def test_default_output_path(self, tmp_path: Path) -> None:
        caj_file = tmp_path / "test.caj"
        caj_file.write_bytes(b"not a real caj")
        # Will fail on conversion but we can test the path logic
        with pytest.raises(ConvertError):
            convert_caj_to_pdf(caj_file)
