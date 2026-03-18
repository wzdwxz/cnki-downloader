"""下载模块单元测试"""

from cnki_downloader.core.downloader import NullProgress, _sanitize_filename


class TestSanitizeFilename:
    def test_normal(self) -> None:
        assert _sanitize_filename("正常标题") == "正常标题"

    def test_special_chars(self) -> None:
        result = _sanitize_filename('文件<名>:含/非法\\字符|测试?*')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_max_length(self) -> None:
        long_name = "a" * 200
        result = _sanitize_filename(long_name, max_length=50)
        assert len(result) == 50

    def test_empty(self) -> None:
        assert _sanitize_filename("") == "untitled"


class TestNullProgress:
    def test_no_error(self) -> None:
        p = NullProgress()
        p.on_progress("t1", 100, 1000)
        from pathlib import Path
        p.on_complete("t1", Path("."))
        p.on_error("t1", Exception("test"))
