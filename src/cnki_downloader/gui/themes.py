"""明暗主题样式表"""

from __future__ import annotations

LIGHT_THEME = """
QMainWindow {
    background-color: #f5f5f5;
}
QWidget#sidebar {
    background-color: #2b2b2b;
    min-width: 200px;
    max-width: 200px;
}
QWidget#sidebar QPushButton {
    background-color: transparent;
    color: #cccccc;
    border: none;
    text-align: left;
    padding: 12px 20px;
    font-size: 14px;
}
QWidget#sidebar QPushButton:hover {
    background-color: #3d3d3d;
    color: #ffffff;
}
QWidget#sidebar QPushButton:checked {
    background-color: #0d6efd;
    color: #ffffff;
}
QWidget#content {
    background-color: #ffffff;
}
QLabel {
    color: #333333;
}
QCheckBox {
    color: #333333;
}
QLineEdit {
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 14px;
    background-color: #ffffff;
    color: #333333;
}
QLineEdit:focus {
    border-color: #0d6efd;
}
QPushButton#primaryBtn {
    background-color: #0d6efd;
    color: white;
    border: none;
    padding: 8px 20px;
    border-radius: 6px;
    font-size: 14px;
}
QPushButton#primaryBtn:hover {
    background-color: #0b5ed7;
}
QPushButton#primaryBtn:pressed {
    background-color: #0a58ca;
}
QTableWidget {
    border: 1px solid #e0e0e0;
    gridline-color: #f0f0f0;
    selection-background-color: #e7f0fd;
    selection-color: #333333;
    font-size: 13px;
    background-color: #ffffff;
    color: #333333;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #f8f9fa;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #dee2e6;
    font-weight: bold;
    color: #333333;
}
QProgressBar {
    border: 1px solid #ddd;
    border-radius: 4px;
    text-align: center;
    height: 20px;
    background-color: #f0f0f0;
}
QProgressBar::chunk {
    background-color: #0d6efd;
    border-radius: 3px;
}
QStatusBar {
    background-color: #f8f9fa;
    border-top: 1px solid #dee2e6;
    color: #333333;
}
QGroupBox {
    border: 1px solid #ddd;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
QComboBox {
    padding: 6px 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: #ffffff;
}
QSpinBox {
    padding: 6px 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: #ffffff;
    color: #333333;
}
QListWidget {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background-color: #ffffff;
}
QPushButton {
    background-color: #f0f0f0;
    color: #333333;
    border: 1px solid #ccc;
    padding: 6px 14px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #e0e0e0;
}
QSplitter::handle {
    background-color: #e0e0e0;
    width: 2px;
}
QDialog {
    background-color: #ffffff;
}
QMessageBox {
    background-color: #ffffff;
}
QGroupBox::title {
    color: #333333;
}
"""

DARK_THEME = """
QMainWindow {
    background-color: #1e1e1e;
}
QWidget#sidebar {
    background-color: #161616;
    min-width: 200px;
    max-width: 200px;
}
QWidget#sidebar QPushButton {
    background-color: transparent;
    color: #aaaaaa;
    border: none;
    text-align: left;
    padding: 12px 20px;
    font-size: 14px;
}
QWidget#sidebar QPushButton:hover {
    background-color: #2a2a2a;
    color: #ffffff;
}
QWidget#sidebar QPushButton:checked {
    background-color: #0d6efd;
    color: #ffffff;
}
QWidget#content {
    background-color: #252526;
}
QLabel {
    color: #cccccc;
}
QLineEdit {
    padding: 8px 12px;
    border: 1px solid #444;
    border-radius: 6px;
    font-size: 14px;
    background-color: #2d2d2d;
    color: #e0e0e0;
}
QLineEdit:focus {
    border-color: #0d6efd;
}
QPushButton {
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #555;
    padding: 6px 14px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #4a4a4a;
}
QPushButton#primaryBtn {
    background-color: #0d6efd;
    color: white;
    border: none;
    padding: 8px 20px;
    border-radius: 6px;
    font-size: 14px;
}
QPushButton#primaryBtn:hover {
    background-color: #0b5ed7;
}
QPushButton#primaryBtn:pressed {
    background-color: #0a58ca;
}
QTableWidget {
    border: 1px solid #444;
    gridline-color: #333;
    selection-background-color: #264f78;
    selection-color: #ffffff;
    font-size: 13px;
    background-color: #1e1e1e;
    color: #cccccc;
    alternate-background-color: #252526;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #2d2d2d;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #444;
    font-weight: bold;
    color: #cccccc;
}
QProgressBar {
    border: 1px solid #444;
    border-radius: 4px;
    text-align: center;
    height: 20px;
    background-color: #2d2d2d;
    color: #cccccc;
}
QProgressBar::chunk {
    background-color: #0d6efd;
    border-radius: 3px;
}
QStatusBar {
    background-color: #1e1e1e;
    border-top: 1px solid #333;
    color: #aaaaaa;
}
QGroupBox {
    border: 1px solid #444;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    color: #cccccc;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
QComboBox {
    padding: 6px 10px;
    border: 1px solid #444;
    border-radius: 4px;
    background-color: #2d2d2d;
    color: #e0e0e0;
}
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #e0e0e0;
    selection-background-color: #264f78;
}
QSpinBox {
    padding: 6px 10px;
    border: 1px solid #444;
    border-radius: 4px;
    background-color: #2d2d2d;
    color: #e0e0e0;
}
QListWidget {
    border: 1px solid #444;
    border-radius: 4px;
    background-color: #1e1e1e;
    color: #cccccc;
}
QListWidget::item:selected {
    background-color: #264f78;
}
QSplitter::handle {
    background-color: #333;
    width: 2px;
}
QCheckBox {
    color: #cccccc;
}
QDialog {
    background-color: #252526;
}
QMessageBox {
    background-color: #252526;
}
"""


def get_theme(name: str) -> str:
    """获取主题样式表。"""
    themes = {
        "light": LIGHT_THEME,
        "dark": DARK_THEME,
    }
    return themes.get(name, LIGHT_THEME)
