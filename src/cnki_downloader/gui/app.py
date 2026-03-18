"""QApplication 初始化、主题配置"""

from __future__ import annotations

import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from cnki_downloader.gui.main_window import MainWindow
from cnki_downloader.gui.themes import get_theme
from cnki_downloader.utils.config import load_config
from cnki_downloader.utils.logging import setup_logging


def run_gui(theme: str = "light") -> None:
    """启动GUI应用。

    Args:
        theme: 主题名称 "light" 或 "dark"
    """
    config = load_config()
    setup_logging(config.log_level)

    app = QApplication(sys.argv)
    app.setApplicationName("CNKI文献下载器")
    app.setStyleSheet(get_theme(theme))

    font = QFont()
    font.setFamily("Microsoft YaHei")
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow(theme=theme)
    window.show()

    sys.exit(app.exec())
