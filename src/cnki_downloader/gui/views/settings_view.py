"""基础设置面板"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from cnki_downloader.utils.config import get_config_dir, load_config


class SettingsView(QWidget):
    """设置视图。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._config = load_config()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("设置")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # 下载设置
        dl_group = QGroupBox("下载设置")
        dl_layout = QFormLayout(dl_group)

        dir_row = QHBoxLayout()
        self._dir_input = QLineEdit(str(self._config.download_dir))
        dir_row.addWidget(self._dir_input, stretch=1)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(browse_btn)
        dl_layout.addRow("下载目录:", dir_row)

        self._concurrent_spin = QSpinBox()
        self._concurrent_spin.setRange(1, 10)
        self._concurrent_spin.setValue(self._config.max_concurrent_downloads)
        dl_layout.addRow("最大并发数:", self._concurrent_spin)

        self._auto_convert_cb = QCheckBox("下载后自动将CAJ转为PDF")
        self._auto_convert_cb.setChecked(self._config.auto_convert_caj)
        dl_layout.addRow("", self._auto_convert_cb)

        layout.addWidget(dl_group)

        # 网络设置
        net_group = QGroupBox("网络设置")
        net_layout = QFormLayout(net_group)

        self._min_delay_input = QLineEdit(str(self._config.min_request_delay))
        self._min_delay_input.setToolTip("最小请求间隔（秒），防止触发反爬")
        net_layout.addRow("最小请求延时 (秒):", self._min_delay_input)

        self._max_delay_input = QLineEdit(str(self._config.max_request_delay))
        net_layout.addRow("最大请求延时 (秒):", self._max_delay_input)

        layout.addWidget(net_group)

        # 保存按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _browse_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择下载目录", str(self._config.download_dir)
        )
        if dir_path:
            self._dir_input.setText(dir_path)

    def _save_settings(self) -> None:
        """将设置保存到TOML配置文件。"""
        config_dir = get_config_dir()
        config_file = config_dir / "config.toml"

        try:
            # 验证延迟值为合法数字
            try:
                min_delay = float(self._min_delay_input.text())
                max_delay = float(self._max_delay_input.text())
            except ValueError:
                QMessageBox.warning(self, "输入错误", "延迟值必须为数字")
                return
            if min_delay > max_delay:
                QMessageBox.warning(self, "输入错误", "最小延迟不能大于最大延迟")
                return

            # 转义路径中的反斜杠以生成合法 TOML
            download_dir = self._dir_input.text().replace("\\", "\\\\")
            lines = [
                f'download_dir = "{download_dir}"',
                f"max_concurrent_downloads = {self._concurrent_spin.value()}",
                f"auto_convert_caj = {'true' if self._auto_convert_cb.isChecked() else 'false'}",
                f"min_request_delay = {min_delay}",
                f"max_request_delay = {max_delay}",
            ]
            config_file.write_text("\n".join(lines), encoding="utf-8")
            QMessageBox.information(self, "成功", "设置已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败: {e}")
