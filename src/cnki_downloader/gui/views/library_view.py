"""文献库面板 — 文献列表、搜索过滤、标签管理、引用导出"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cnki_downloader.core.export import (
    export_to_file,
)
from cnki_downloader.gui.viewmodels.library_vm import LibraryViewModel
from cnki_downloader.models.paper import Paper


class LibraryView(QWidget):
    """文献库视图。"""

    def __init__(self, library_vm: LibraryViewModel | None = None, parent=None) -> None:
        super().__init__(parent)
        self._vm = library_vm
        self._init_ui()
        if self._vm:
            self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 标题行
        header = QHBoxLayout()
        title = QLabel("文献库")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        header.addWidget(title)
        header.addStretch()

        self._count_label = QLabel("共 0 篇")
        self._count_label.setStyleSheet("color: #888; font-size: 13px;")
        header.addWidget(self._count_label)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._on_refresh)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # 搜索/过滤栏
        filter_bar = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索文献库...")
        self._search_input.returnPressed.connect(self._on_search)
        filter_bar.addWidget(self._search_input, stretch=1)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["全部", "收藏"])
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self._filter_combo)

        search_btn = QPushButton("搜索")
        search_btn.setObjectName("primaryBtn")
        search_btn.clicked.connect(self._on_search)
        filter_bar.addWidget(search_btn)
        layout.addLayout(filter_bar)

        # 主区域：左侧标签/分类 + 右侧文献表
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧面板：标签和分类
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)

        # 标签列表
        tag_group = QGroupBox("标签")
        tag_layout = QVBoxLayout(tag_group)
        self._tag_list = QListWidget()
        self._tag_list.setMaximumHeight(150)
        tag_layout.addWidget(self._tag_list)
        left_layout.addWidget(tag_group)

        # 分类树
        cat_group = QGroupBox("分类")
        cat_layout = QVBoxLayout(cat_group)
        self._category_list = QListWidget()
        cat_layout.addWidget(self._category_list)
        left_layout.addWidget(cat_group)

        left_panel.setMaximumWidth(200)
        splitter.addWidget(left_panel)

        # 右侧：文献表格
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["标题", "作者", "期刊", "日期", "收藏", "文件"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 130)
        self._table.setColumnWidth(2, 120)
        self._table.setColumnWidth(3, 90)
        self._table.setColumnWidth(4, 45)
        self._table.setColumnWidth(5, 80)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        right_layout.addWidget(self._table)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

        # 底部操作栏
        actions = QHBoxLayout()

        self._export_combo = QComboBox()
        self._export_combo.addItems(["BibTeX", "EndNote", "GB/T 7714"])
        actions.addWidget(QLabel("导出格式:"))
        actions.addWidget(self._export_combo)

        export_btn = QPushButton("导出引用")
        export_btn.setObjectName("primaryBtn")
        export_btn.clicked.connect(self._on_export)
        actions.addWidget(export_btn)

        actions.addStretch()

        export_all_btn = QPushButton("导出全部")
        export_all_btn.clicked.connect(self._on_export_all)
        actions.addWidget(export_all_btn)

        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._vm.papers_changed.connect(self._on_papers_changed)
        self._vm.tags_changed.connect(self._on_tags_changed)
        self._vm.categories_changed.connect(self._on_categories_changed)
        self._vm.total_changed.connect(self._on_total_changed)
        self._vm.error_occurred.connect(self._on_error)

    def _on_refresh(self) -> None:
        if self._vm:
            self._vm.refresh()

    def _on_search(self) -> None:
        keyword = self._search_input.text().strip()
        if self._vm:
            self._vm.refresh(keyword=keyword)

    def _on_filter_changed(self, index: int) -> None:
        if self._vm:
            self._vm.refresh(favorites_only=(index == 1))

    def _on_papers_changed(self, papers: list[Paper]) -> None:
        self._table.setRowCount(len(papers))
        for row, paper in enumerate(papers):
            self._table.setItem(row, 0, QTableWidgetItem(paper.title))
            authors = ", ".join(paper.authors[:2])
            if len(paper.authors) > 2:
                authors += " 等"
            self._table.setItem(row, 1, QTableWidgetItem(authors))
            self._table.setItem(row, 2, QTableWidgetItem(paper.journal))
            self._table.setItem(row, 3, QTableWidgetItem(paper.publish_date))

            fav_item = QTableWidgetItem("★" if paper.is_favorite else "")
            fav_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if paper.is_favorite:
                fav_item.setForeground(Qt.GlobalColor.red)
            self._table.setItem(row, 4, fav_item)

            has_file = "有" if paper.local_path else "--"
            self._table.setItem(row, 5, QTableWidgetItem(has_file))

    def _on_tags_changed(self, tags: list[dict]) -> None:
        self._tag_list.clear()
        for tag in tags:
            item = QListWidgetItem(f"● {tag['name']}")
            self._tag_list.addItem(item)

    def _on_categories_changed(self, categories: list[dict]) -> None:
        self._category_list.clear()
        for cat in categories:
            indent = "  " if cat.get("parent_id") else ""
            item = QListWidgetItem(f"{indent}{cat['name']}")
            self._category_list.addItem(item)

    def _on_total_changed(self, total: int) -> None:
        self._count_label.setText(f"共 {total} 篇")

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "错误", msg)

    def _get_selected_papers(self) -> list[Paper]:
        if not self._vm:
            return []
        rows = set()
        for item in self._table.selectedItems():
            rows.add(item.row())
        return [self._vm.papers[r] for r in sorted(rows) if r < len(self._vm.papers)]

    def _on_export(self) -> None:
        papers = self._get_selected_papers()
        if not papers:
            QMessageBox.information(self, "提示", "请先选择要导出的文献")
            return
        self._do_export(papers)

    def _on_export_all(self) -> None:
        if not self._vm or not self._vm.papers:
            QMessageBox.information(self, "提示", "文献库为空")
            return
        self._do_export(self._vm.papers)

    def _do_export(self, papers: list[Paper]) -> None:
        fmt_map = {"BibTeX": "bibtex", "EndNote": "endnote", "GB/T 7714": "gbt7714"}
        fmt = fmt_map.get(self._export_combo.currentText(), "bibtex")

        ext_map = {"bibtex": ".bib", "endnote": ".enw", "gbt7714": ".txt"}
        ext = ext_map.get(fmt, ".txt")

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出引用", f"references{ext}", f"引用文件 (*{ext})"
        )
        if not file_path:
            return

        try:
            path = export_to_file(papers, Path(file_path), fmt)
            QMessageBox.information(
                self, "导出成功", f"已导出 {len(papers)} 篇文献引用到:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
