"""搜索面板 — 关键词输入、高级搜索、结果表格"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cnki_downloader.gui.viewmodels.search_vm import SearchViewModel
from cnki_downloader.models.paper import Paper


class SearchView(QWidget):
    """搜索视图。"""

    def __init__(self, search_vm: SearchViewModel, parent=None) -> None:
        super().__init__(parent)
        self._vm = search_vm
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title = QLabel("文献搜索")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # 搜索栏
        search_bar = QHBoxLayout()
        self._keyword_input = QLineEdit()
        self._keyword_input.setPlaceholderText("输入搜索关键词...")
        self._keyword_input.returnPressed.connect(self._on_search)
        search_bar.addWidget(self._keyword_input, stretch=1)

        self._search_btn = QPushButton("搜索")
        self._search_btn.setObjectName("primaryBtn")
        self._search_btn.clicked.connect(self._on_search)
        search_bar.addWidget(self._search_btn)

        self._advanced_btn = QPushButton("高级搜索 ▼")
        self._advanced_btn.setCheckable(True)
        self._advanced_btn.clicked.connect(self._toggle_advanced)
        search_bar.addWidget(self._advanced_btn)

        layout.addLayout(search_bar)

        # 高级搜索面板（默认隐藏）
        self._advanced_panel = QGroupBox()
        advanced_layout = QFormLayout(self._advanced_panel)
        self._author_input = QLineEdit()
        self._author_input.setPlaceholderText("作者姓名")
        advanced_layout.addRow("作者:", self._author_input)
        self._journal_input = QLineEdit()
        self._journal_input.setPlaceholderText("期刊名称")
        advanced_layout.addRow("期刊:", self._journal_input)
        self._date_from_input = QLineEdit()
        self._date_from_input.setPlaceholderText("YYYY-MM-DD")
        advanced_layout.addRow("起始日期:", self._date_from_input)
        self._date_to_input = QLineEdit()
        self._date_to_input.setPlaceholderText("YYYY-MM-DD")
        advanced_layout.addRow("截止日期:", self._date_to_input)
        self._advanced_panel.setVisible(False)
        layout.addWidget(self._advanced_panel)

        # 状态行
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(self._status_label)

        # 结果表格
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["", "标题", "作者", "期刊", "日期"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 40)
        self._table.setColumnWidth(2, 150)
        self._table.setColumnWidth(3, 150)
        self._table.setColumnWidth(4, 100)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, stretch=1)

        # 分页栏
        pager = QHBoxLayout()
        pager.addStretch()
        self._prev_btn = QPushButton("◀ 上一页")
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._vm.prev_page)
        pager.addWidget(self._prev_btn)
        self._page_label = QLabel("第 1 页")
        self._page_label.setStyleSheet("margin: 0 12px;")
        pager.addWidget(self._page_label)
        self._next_btn = QPushButton("下一页 ▶")
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._vm.next_page)
        pager.addWidget(self._next_btn)
        pager.addStretch()
        layout.addLayout(pager)

    def _connect_signals(self) -> None:
        self._vm.loading_changed.connect(self._on_loading_changed)
        self._vm.results_changed.connect(self._on_results_changed)
        self._vm.total_count_changed.connect(self._on_total_changed)
        self._vm.page_changed.connect(self._on_page_changed)
        self._vm.error_occurred.connect(self._on_error)

    def _on_search(self) -> None:
        keyword = self._keyword_input.text().strip()
        if not keyword:
            return
        self._vm.search(
            keyword=keyword,
            author=self._author_input.text().strip(),
            journal=self._journal_input.text().strip(),
            start_date=self._date_from_input.text().strip(),
            end_date=self._date_to_input.text().strip(),
        )

    def _toggle_advanced(self, checked: bool) -> None:
        self._advanced_panel.setVisible(checked)
        self._advanced_btn.setText("高级搜索 ▲" if checked else "高级搜索 ▼")

    def _on_loading_changed(self, loading: bool) -> None:
        self._search_btn.setEnabled(not loading)
        self._keyword_input.setEnabled(not loading)
        self._status_label.setText("正在搜索..." if loading else "")

    def _on_results_changed(self, papers: list[Paper]) -> None:
        self._table.setRowCount(len(papers))
        for row, paper in enumerate(papers):
            self._table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self._table.setItem(row, 1, QTableWidgetItem(paper.title))
            self._table.setItem(row, 2, QTableWidgetItem(", ".join(paper.authors[:3])))
            self._table.setItem(row, 3, QTableWidgetItem(paper.journal))
            self._table.setItem(row, 4, QTableWidgetItem(paper.publish_date))

    def _on_total_changed(self, total: int) -> None:
        self._status_label.setText(f"共找到 {total} 条结果")

    def _on_page_changed(self, page: int) -> None:
        self._page_label.setText(f"第 {page} 页")
        self._prev_btn.setEnabled(page > 1)
        has_more = page * 20 < self._vm.total_count
        self._next_btn.setEnabled(has_more)

    def _on_error(self, msg: str) -> None:
        self._status_label.setText("")
        QMessageBox.warning(self, "搜索错误", msg)

    def get_selected_papers(self) -> list[Paper]:
        """获取表格中选中的文献。"""
        rows = set()
        for item in self._table.selectedItems():
            rows.add(item.row())
        return [self._vm.papers[r] for r in sorted(rows) if r < len(self._vm.papers)]
