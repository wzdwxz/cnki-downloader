"""搜索 ViewModel — 管理搜索状态，通过Qt信号驱动UI更新"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from cnki_downloader.gui.workers.browser_thread import BrowserThread
from cnki_downloader.gui.workers.search_worker import SearchWorker
from cnki_downloader.models.paper import Paper
from cnki_downloader.models.search_result import SearchQuery, SearchResult


class SearchViewModel(QObject):
    """搜索视图模型。"""

    # 状态信号
    loading_changed = pyqtSignal(bool)
    results_changed = pyqtSignal(list)      # list[Paper]
    total_count_changed = pyqtSignal(int)
    error_occurred = pyqtSignal(str)
    page_changed = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._papers: list[Paper] = []
        self._total_count: int = 0
        self._current_page: int = 1
        self._current_query: SearchQuery | None = None
        self._worker: SearchWorker | None = None
        self._loading: bool = False
        self._source_types: list[str] = []

        # 持久化浏览器线程
        self._browser_thread = BrowserThread()
        self._browser_thread.start()

    @property
    def papers(self) -> list[Paper]:
        return self._papers

    @property
    def total_count(self) -> int:
        return self._total_count

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def is_loading(self) -> bool:
        return self._loading

    def search(
        self,
        keyword: str,
        author: str = "",
        journal: str = "",
        start_date: str = "",
        end_date: str = "",
        page: int = 1,
        source_types: list[str] | None = None,
    ) -> None:
        """发起搜索。"""
        if self._loading:
            return

        self._current_query = SearchQuery(
            keyword=keyword,
            author=author,
            journal=journal,
            start_date=start_date,
            end_date=end_date,
            page=page,
        )
        self._current_page = page
        self._source_types = source_types or []

        self._set_loading(True)

        self._worker = SearchWorker(
            self._current_query,
            self._browser_thread,
            source_types=self._source_types,
        )
        self._worker.finished.connect(self._on_search_finished)
        self._worker.error.connect(self._on_search_error)
        self._worker.start()

    def cancel(self) -> None:
        """Cancel running search and shut down browser thread."""
        if self._worker and self._worker.isRunning():
            self._worker.wait(3000)
            if self._worker.isRunning():
                self._worker.terminate()
                self._worker.wait(1000)
            self._loading = False
            self.loading_changed.emit(False)
        self._browser_thread.shutdown()

    def next_page(self) -> None:
        if self._current_query:
            self.search(
                keyword=self._current_query.keyword,
                author=self._current_query.author,
                journal=self._current_query.journal,
                start_date=self._current_query.start_date,
                end_date=self._current_query.end_date,
                page=self._current_page + 1,
                source_types=self._source_types,
            )

    def prev_page(self) -> None:
        if self._current_query and self._current_page > 1:
            self.search(
                keyword=self._current_query.keyword,
                author=self._current_query.author,
                journal=self._current_query.journal,
                start_date=self._current_query.start_date,
                end_date=self._current_query.end_date,
                page=self._current_page - 1,
                source_types=self._source_types,
            )

    def _set_loading(self, loading: bool) -> None:
        self._loading = loading
        self.loading_changed.emit(loading)

    def _on_search_finished(self, result: SearchResult) -> None:
        self._papers = result.papers
        self._total_count = result.total_count
        self._current_page = result.page
        self._set_loading(False)
        self.results_changed.emit(self._papers)
        self.total_count_changed.emit(self._total_count)
        self.page_changed.emit(self._current_page)

    def _on_search_error(self, error_msg: str) -> None:
        self._set_loading(False)
        self.error_occurred.emit(error_msg)
