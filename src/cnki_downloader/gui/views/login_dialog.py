"""登录对话框"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class LoginDialog(QDialog):
    """知网账号登录对话框。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录知网")
        self.setFixedSize(480, 320)
        self._username: str = ""
        self._password: str = ""
        self._remember: bool = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        title = QLabel("登录知网账号")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel("使用知网个人账号登录，获取下载权限")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(12)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("手机号/邮箱")
        self._username_input.setMinimumWidth(320)
        form.addRow("账号:", self._username_input)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("密码")
        self._password_input.setMinimumWidth(320)
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("密码:", self._password_input)

        layout.addLayout(form)

        self._remember_cb = QCheckBox("记住密码（保存到系统密钥环）")
        layout.addWidget(self._remember_cb)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        login_btn = QPushButton("登录")
        login_btn.setObjectName("primaryBtn")
        login_btn.clicked.connect(self._on_login)
        login_btn.setDefault(True)
        btn_layout.addWidget(login_btn)

        layout.addLayout(btn_layout)

    def _on_login(self) -> None:
        username = self._username_input.text().strip()
        password = self._password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入账号和密码")
            return

        self._username = username
        self._password = password
        self._remember = self._remember_cb.isChecked()
        self.accept()

    @property
    def username(self) -> str:
        return self._username

    @property
    def password(self) -> str:
        return self._password

    @property
    def remember(self) -> bool:
        return self._remember
