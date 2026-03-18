"""搜索面板 — 关键词输入、高级搜索、结果表格（带勾选）"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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

    download_requested = pyqtSignal(list)       # list[Paper]
    paper_double_clicked = pyqtSignal(object)   # Paper

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
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
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

        # 文献类型勾选
        type_row = QHBoxLayout()
        self._type_checkboxes: dict[str, QCheckBox] = {}
        for type_name in ["期刊", "博士", "硕士", "会议", "报纸"]:
            cb = QCheckBox(type_name)
            self._type_checkboxes[type_name] = cb
            type_row.addWidget(cb)
        type_row.addStretch()
        advanced_layout.addRow("文献类型:", type_row)

        self._advanced_panel.setVisible(False)
        layout.addWidget(self._advanced_panel)

        # 操作栏：全选 + 状态 + 下载按钮
        action_bar = QHBoxLayout()
        self._select_all_cb = QCheckBox("全选")
        self._select_all_cb.stateChanged.connect(self._on_select_all)
        action_bar.addWidget(self._select_all_cb)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 13px;")
        action_bar.addWidget(self._status_label, stretch=1)

        self._download_btn = QPushButton("下载选中")
        self._download_btn.setObjectName("primaryBtn")
        self._download_btn.clicked.connect(self._on_download_selected)
        self._download_btn.setEnabled(False)
        action_bar.addWidget(self._download_btn)

        layout.addLayout(action_bar)

        # 结果表格
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["", "序号", "标题", "作者", "期刊", "日期"]
        )
        # 勾选列
        self._table.setColumnWidth(0, 35)
        # 序号列
        self._table.setColumnWidth(1, 40)
        # 标题列自适应
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.setColumnWidth(3, 150)
        self._table.setColumnWidth(4, 150)
        self._table.setColumnWidth(5, 100)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.doubleClicked.connect(self._on_table_double_clicked)
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
        # 收集勾选的文献类型
        source_types = [
            name for name, cb in self._type_checkboxes.items()
            if cb.isChecked()
        ]
        self._vm.search(
            keyword=keyword,
            author=self._author_input.text().strip(),
            journal=self._journal_input.text().strip(),
            start_date=self._date_from_input.text().strip(),
            end_date=self._date_to_input.text().strip(),
            source_types=source_types if source_types else None,
        )

    def _toggle_advanced(self, checked: bool) -> None:
        self._advanced_panel.setVisible(checked)
        self._advanced_btn.setText("高级搜索 ▲" if checked else "高级搜索 ▼")

    def _on_loading_changed(self, loading: bool) -> None:
        self._search_btn.setEnabled(not loading)
        self._keyword_input.setEnabled(not loading)
        self._status_label.setText("正在搜索..." if loading else "")

    def _on_results_changed(self, papers: list[Paper]) -> None:
        # 暂时断开全选信号，避免填充表格时触发
        self._select_all_cb.blockSignals(True)
        self._select_all_cb.setChecked(False)
        self._select_all_cb.blockSignals(False)

        self._table.setRowCount(len(papers))
        for row, paper in enumerate(papers):
            # 勾选框
            cb_item = QTableWidgetItem()
            cb_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            cb_item.setCheckState(Qt.CheckState.Unchecked)
            self._table.setItem(row, 0, cb_item)

            # 序号
            self._table.setItem(row, 1, QTableWidgetItem(str(row + 1)))
            # 标题
            self._table.setItem(row, 2, QTableWidgetItem(paper.title))
            # 作者
            self._table.setItem(
                row, 3, QTableWidgetItem(", ".join(paper.authors[:3]))
            )
            # 期刊
            self._table.setItem(row, 4, QTableWidgetItem(paper.journal))
            # 日期
            self._table.setItem(row, 5, QTableWidgetItem(paper.publish_date))

        self._download_btn.setEnabled(False)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """勾选框变化时更新下载按钮和全选框状态。"""
        if item.column() != 0:
            return
        checked_count = self._get_checked_count()
        total = self._table.rowCount()
        self._download_btn.setEnabled(checked_count > 0)

        # 更新全选框状态（不触发信号）
        self._select_all_cb.blockSignals(True)
        if checked_count == 0:
            self._select_all_cb.setCheckState(Qt.CheckState.Unchecked)
        elif checked_count == total:
            self._select_all_cb.setCheckState(Qt.CheckState.Checked)
        else:
            self._select_all_cb.setCheckState(Qt.CheckState.PartiallyChecked)
        self._select_all_cb.blockSignals(False)

    def _on_table_double_clicked(self, index) -> None:
        """Re-emit table double-click as a typed Paper signal."""
        row = index.row()
        papers = self._vm.papers
        if 0 <= row < len(papers):
            self.paper_double_clicked.emit(papers[row])

    def _on_select_all(self, state: int) -> None:
        """全选/取消全选。"""
        check = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item:
                item.setCheckState(check)
        self._table.blockSignals(False)
        self._download_btn.setEnabled(state != 0 and self._table.rowCount() > 0)

    def _get_checked_count(self) -> int:
        count = 0
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                count += 1
        return count

    def _on_download_selected(self) -> None:
        """下载勾选的文献。"""
        papers = self.get_selected_papers()
        if not papers:
            QMessageBox.information(self, "提示", "请先勾选要下载的文献")
            return
        self.download_requested.emit(papers)

    def _on_total_changed(self, total: int) -> None:
        self._status_label.setText(f"共找到 {total} 条结果")

    def _on_page_changed(self, page: int) -> None:
        total = self._vm.total_count
        page_size = 20
        total_pages = max(1, (total + page_size - 1) // page_size)
        self._page_label.setText(f"第 {page} / {total_pages} 页")
        self._prev_btn.setEnabled(page > 1)
        self._next_btn.setEnabled(page < total_pages)

    def _on_error(self, msg: str) -> None:
        self._status_label.setText("")
        QMessageBox.warning(self, "搜索错误", msg)

    def get_selected_papers(self) -> list[Paper]:
        """获取勾选的文献列表。"""
        selected = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                if row < len(self._vm.papers):
                    selected.append(self._vm.papers[row])
        return selected
