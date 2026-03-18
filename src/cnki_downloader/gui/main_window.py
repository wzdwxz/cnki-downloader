"""主窗口 — 侧边栏导航 + 内容区"""

from __future__ import annotations

import asyncio

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from cnki_downloader.core.auth import check_campus_network, login
from cnki_downloader.core.session import SessionManager
from cnki_downloader.gui.viewmodels.download_vm import DownloadViewModel
from cnki_downloader.gui.viewmodels.library_vm import LibraryViewModel
from cnki_downloader.gui.viewmodels.search_vm import SearchViewModel
from cnki_downloader.gui.views.download_view import DownloadView
from cnki_downloader.gui.views.library_view import LibraryView
from cnki_downloader.gui.views.login_dialog import LoginDialog
from cnki_downloader.gui.views.search_view import SearchView
from cnki_downloader.gui.views.settings_view import SettingsView
from cnki_downloader.models.user import Credential


class MainWindow(QMainWindow):
    """应用主窗口。"""

    def __init__(self, theme: str = "light") -> None:
        super().__init__()
        self.setWindowTitle("CNKI文献下载器")
        self.setMinimumSize(1000, 650)
        self.resize(1200, 750)
        self._current_theme = theme

        # ViewModels
        self._search_vm = SearchViewModel()
        self._download_vm = DownloadViewModel()
        self._library_vm = LibraryViewModel()

        self._init_ui()
        self._init_statusbar()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 侧边栏 ===
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo
        logo = QLabel("CNKI下载器")
        logo.setStyleSheet(
            "color: white; font-size: 16px; font-weight: bold; padding: 20px;"
        )
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo)

        # 导航按钮
        self._nav_buttons: list[QPushButton] = []
        nav_items = [
            ("搜索文献", 0),
            ("下载管理", 1),
            ("文献库", 2),
            ("设置", 3),
        ]
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, i=index: self._switch_page(i))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # 主题切换
        theme_label = "切换暗色主题" if self._current_theme == "light" else "切换亮色主题"
        self._theme_btn = QPushButton(theme_label)
        self._theme_btn.setStyleSheet(
            "color: #888; border-top: 1px solid #444; padding: 10px 20px; font-size: 12px;"
        )
        self._theme_btn.clicked.connect(self._toggle_theme)
        sidebar_layout.addWidget(self._theme_btn)

        # 登录按钮
        self._login_btn = QPushButton("登录账号")
        self._login_btn.setStyleSheet(
            "color: #aaa; border-top: 1px solid #444; padding: 12px 20px;"
        )
        self._login_btn.clicked.connect(self._show_login)
        sidebar_layout.addWidget(self._login_btn)

        main_layout.addWidget(sidebar)

        # === 内容区 ===
        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()

        # 页面
        self._search_view = SearchView(self._search_vm)
        self._download_view = DownloadView(self._download_vm)
        self._library_view = LibraryView(self._library_vm)
        self._settings_view = SettingsView()

        self._stack.addWidget(self._search_view)       # 0
        self._stack.addWidget(self._download_view)      # 1
        self._stack.addWidget(self._library_view)       # 2
        self._stack.addWidget(self._settings_view)      # 3

        content_layout.addWidget(self._stack)
        main_layout.addWidget(content, stretch=1)

        # 默认选中搜索页
        self._switch_page(0)

        # 连接搜索->下载
        self._connect_cross_view_signals()

    def _init_statusbar(self) -> None:
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self._network_label = QLabel("网络: 检测中...")
        status_bar.addPermanentWidget(self._network_label)

        # 异步检测网络
        self._check_network_thread = NetworkCheckThread()
        self._check_network_thread.result.connect(self._on_network_checked)
        self._check_network_thread.start()

    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    def _connect_cross_view_signals(self) -> None:
        """连接跨视图交互：搜索结果中下载选中文献。"""
        # 在搜索页双击结果行时，跳转到下载
        self._search_view._table.doubleClicked.connect(self._on_paper_double_clicked)

    def _on_paper_double_clicked(self, index) -> None:
        papers = self._search_view.get_selected_papers()
        if papers:
            self._download_vm.download(papers)
            self._switch_page(1)

    def _show_login(self) -> None:
        dialog = LoginDialog(self)
        if dialog.exec() == LoginDialog.DialogCode.Accepted:
            self._do_login(dialog.username, dialog.password, dialog.remember)

    def _do_login(self, username: str, password: str, remember: bool) -> None:
        self._login_thread = LoginThread(username, password, remember)
        self._login_thread.success.connect(self._on_login_success)
        self._login_thread.error.connect(self._on_login_error)
        self._login_thread.start()
        self._login_btn.setText("登录中...")
        self._login_btn.setEnabled(False)

    def _on_login_success(self, username: str) -> None:
        self._login_btn.setText(f"已登录: {username}")
        self._login_btn.setEnabled(True)
        self.statusBar().showMessage("登录成功", 3000)

    def _on_login_error(self, error_msg: str) -> None:
        self._login_btn.setText("登录账号")
        self._login_btn.setEnabled(True)
        QMessageBox.warning(self, "登录失败", error_msg)

    def _toggle_theme(self) -> None:
        from cnki_downloader.gui.themes import get_theme

        if self._current_theme == "light":
            self._current_theme = "dark"
            self._theme_btn.setText("切换亮色主题")
        else:
            self._current_theme = "light"
            self._theme_btn.setText("切换暗色主题")

        app = QMainWindow.sender(self)  # noqa
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(get_theme(self._current_theme))

    def _on_network_checked(self, has_access: bool) -> None:
        if has_access:
            self._network_label.setText("网络: 已连接校园网")
            self._network_label.setStyleSheet("color: green;")
        else:
            self._network_label.setText("网络: 未连接校园网")
            self._network_label.setStyleSheet("color: #cc7700;")


class NetworkCheckThread(QThread):
    """后台检查校园网连接。"""

    result = pyqtSignal(bool)

    def run(self) -> None:
        try:
            has = asyncio.run(self._check())
            self.result.emit(has)
        except Exception:
            self.result.emit(False)

    async def _check(self) -> bool:
        async with SessionManager(min_delay=0, max_delay=0) as session:
            return await check_campus_network(session)


class LoginThread(QThread):
    """后台执行登录。"""

    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, username: str, password: str, remember: bool) -> None:
        super().__init__()
        self._username = username
        self._password = password
        self._remember = remember

    def run(self) -> None:
        try:
            asyncio.run(self._login())
            self.success.emit(self._username)
        except Exception as e:
            self.error.emit(str(e))

    async def _login(self) -> None:
        from cnki_downloader.core.auth import save_credential

        async with SessionManager() as session:
            credential = Credential(
                username=self._username,
                password=self._password,
                auth_type="account",
            )
            await login(session, credential)
            if self._remember:
                save_credential(credential)
