# GUI Architecture Fixes: Browser Lifecycle & View Decoupling

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two architectural issues in the GUI layer: (1) the broken persistent browser pattern in SearchWorker that uses module-level globals incompatible with `asyncio.run()`, and (2) cross-view private member access violations that break MVVM encapsulation.

**Architecture:** Replace module-level browser globals with per-worker browser instances (matching DownloadWorker's proven pattern). Add proper signals to SearchView and MainWindow to eliminate all private member access across component boundaries. The SearchViewModel already has a clean signal-based interface — we extend this pattern to cross-view communication.

**Tech Stack:** PyQt6 (pyqtSignal/pyqtSlot), Playwright (async API), asyncio

**Rollback:** Tasks 3 and 4 are tightly coupled — if Task 3 is committed but Task 4 fails, the app breaks. If Task 4 fails, revert both: `git revert HEAD HEAD~1`. Tasks 1–2 are independent and safe to land alone.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/cnki_downloader/gui/workers/search_worker.py` | Modify | Remove module-level browser globals; each worker owns its browser |
| `src/cnki_downloader/gui/views/search_view.py` | Modify | Add `download_requested` and `paper_double_clicked` signals |
| `src/cnki_downloader/gui/main_window.py` | Modify | Connect to SearchView signals instead of accessing private members; add `closeEvent` for cleanup |
| `src/cnki_downloader/gui/viewmodels/search_vm.py` | Modify (minor) | Add `cancel()` public method for clean shutdown |
| `tests/unit/test_search_worker_browser.py` | Create | Test that SearchWorker creates/closes browser per run |
| `tests/unit/test_search_view_signals.py` | Create | Test that SearchView emits proper signals |

---

## Task 1: Remove Module-Level Browser Globals from SearchWorker

**Why:** `_browser`, `_context`, `_page` are module-level globals. Each `asyncio.run()` creates and destroys an event loop, so Playwright objects created in one `asyncio.run()` belong to a dead event loop when reused in the next call. The `close_browser()` function is also never called anywhere.

**Files:**
- Modify: `src/cnki_downloader/gui/workers/search_worker.py:28-78` (globals + `_get_page` + `close_browser`)
- Modify: `src/cnki_downloader/gui/workers/search_worker.py:114-208` (the `_search` method)
- Create: `tests/unit/test_search_worker_browser.py`

- [ ] **Step 1: Write test verifying no module-level browser globals exist and browser is scoped per search**

```python
"""tests/unit/test_search_worker_browser.py"""
import pytest


def test_no_module_level_browser_globals():
    """Module should not have mutable browser globals."""
    import cnki_downloader.gui.workers.search_worker as mod

    assert not hasattr(mod, "_browser"), "_browser global should be removed"
    assert not hasattr(mod, "_context"), "_context global should be removed"
    assert not hasattr(mod, "_page"), "_page global should be removed"


def test_no_get_page_function():
    """Module should not have the _get_page helper."""
    import cnki_downloader.gui.workers.search_worker as mod

    assert not hasattr(mod, "_get_page"), "_get_page function should be removed"


def test_no_close_browser_function():
    """Module should not have the close_browser helper."""
    import cnki_downloader.gui.workers.search_worker as mod

    assert not hasattr(mod, "close_browser"), "close_browser function should be removed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_search_worker_browser.py -v`
Expected: FAIL — module still has `_browser` global, `_get_page`, `close_browser`

- [ ] **Step 3: Rewrite SearchWorker._search() to use per-invocation browser**

Delete lines 28–78 entirely (the module-level globals `_browser`, `_context`, `_page`, the `_get_page()` function, and the `close_browser()` function). Keep `_get_cookie_file()` (lines 19–25) and `SOURCE_TYPE_CODES` (lines 82–88).

Then rewrite `_search()`. The existing code (lines 114–208) builds the URL inline — keep that exact logic but wrap it in `async with async_playwright() as pw:` with a `try/finally` for `browser.close()`. The key structural change:

```python
async def _search(self) -> SearchResult:
    """执行浏览器搜索，每次创建独立的浏览器实例。"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "搜索需要 Playwright，请运行：\n"
            "pip install playwright && python -m playwright install chromium"
        )

    from urllib.parse import quote

    query = self._query
    cookie_file = _get_cookie_file()

    ctx_kwargs: dict = {
        "viewport": {"width": 1400, "height": 900},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    if cookie_file.exists():
        try:
            data = json.loads(cookie_file.read_text(encoding="utf-8"))
            if data.get("cookies"):
                ctx_kwargs["storage_state"] = str(cookie_file)
        except Exception:
            pass

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()

            # === URL construction (keep existing inline logic exactly) ===
            search_url = (
                f"https://kns.cnki.net/kns8s/defaultresult/index"
                f"?kw={quote(query.keyword)}&korder=SU"
            )
            if query.start_date:
                year_match = re.search(r"(\d{4})", query.start_date)
                if year_match:
                    search_url += f"&date_from={year_match.group(1)}"
            if query.end_date:
                year_match = re.search(r"(\d{4})", query.end_date)
                if year_match:
                    search_url += f"&date_to={year_match.group(1)}"

            if self._source_types:
                codes = [
                    SOURCE_TYPE_CODES[t]
                    for t in self._source_types
                    if t in SOURCE_TYPE_CODES
                ]
                if codes:
                    search_url += f"&bCKY3={','.join(codes)}"

            await page.goto(search_url, timeout=30000)
            await asyncio.sleep(3)

            # === Captcha check (keep existing logic) ===
            if "verify" in page.url:
                raise RuntimeError(
                    "知网需要验证，请先通过侧边栏「机构登录」完成认证"
                )

            # === Pagination (keep existing logic) ===
            if query.page > 1:
                for target_page in range(2, query.page + 1):
                    try:
                        next_btn = page.locator(
                            f"a[data-page='{target_page}']"
                        ).first
                        if not await next_btn.is_visible(timeout=2000):
                            next_btn = page.locator("a#PageNext, a.next").first
                        await next_btn.click()
                        await asyncio.sleep(3)
                    except Exception:
                        break

            # === Parse total count (keep existing selector) ===
            total_count = 0
            try:
                count_el = page.locator(
                    ".pagerTitleCell em, .result-count"
                ).first
                if await count_el.is_visible(timeout=3000):
                    count_text = await count_el.inner_text()
                    m = re.search(r"([\d,]+)", count_text)
                    if m:
                        total_count = int(m.group(1).replace(",", ""))
            except Exception:
                pass

            # === Parse results (keep existing method call) ===
            papers = await self._parse_results(page)

            if self._source_types:
                papers = [
                    p for p in papers
                    if p.doc_type in self._source_types
                    or not p.doc_type
                ]

            if not total_count:
                total_count = len(papers)

            return SearchResult(
                query=query,
                papers=papers,
                total_count=total_count,
                page=query.page,
            )
        finally:
            await browser.close()
```

Note: This is the *complete* replacement for `_search()`. The URL building, captcha check, pagination, count parsing, and result parsing logic are all preserved verbatim from the existing code (lines 128–208). The only structural change is wrapping in `async with async_playwright()` + `try/finally browser.close()` instead of calling the module-level `_get_page()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_search_worker_browser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cnki_downloader/gui/workers/search_worker.py tests/unit/test_search_worker_browser.py
git commit -m "fix: replace module-level browser globals with per-search instances

Each SearchWorker._search() now creates and closes its own Playwright
browser, matching DownloadWorker's pattern. Eliminates event loop
mismatch bug and thread safety issues with shared globals."
```

---

## Task 2: Add SearchViewModel.cancel() and MainWindow closeEvent

**Why:** If the user closes the app mid-search, the browser process leaks. MainWindow needs a `closeEvent` to request graceful shutdown. But accessing `_search_vm._worker` directly violates MVVM — so we add a public `cancel()` method to SearchViewModel. Note: `QThread.quit()` won't stop `asyncio.run()` — we use `QThread.wait()` with a timeout and `terminate()` as last resort.

**Files:**
- Modify: `src/cnki_downloader/gui/viewmodels/search_vm.py` (add `cancel()`)
- Modify: `src/cnki_downloader/gui/main_window.py` (add `closeEvent`)

- [ ] **Step 1: Add cancel() to SearchViewModel**

In `src/cnki_downloader/gui/viewmodels/search_vm.py`, add after the existing `search()` method:

```python
def cancel(self) -> None:
    """Cancel running search and wait for worker to finish."""
    if self._worker and self._worker.isRunning():
        self._worker.wait(3000)
        if self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(1000)
        self._loading = False
        self.loading_changed.emit(False)
```

- [ ] **Step 2: Add closeEvent to MainWindow**

In `src/cnki_downloader/gui/main_window.py`, add before the inner thread classes (before `class NetworkCheckThread`):

```python
def closeEvent(self, event) -> None:
    """Ensure any running search worker is stopped before exit."""
    if hasattr(self, '_search_vm'):
        self._search_vm.cancel()
    super().closeEvent(event)
```

- [ ] **Step 3: Verify import works**

Run: `python -c "from cnki_downloader.gui.main_window import MainWindow; print('import OK')"`
Expected: `import OK`

- [ ] **Step 4: Commit**

```bash
git add src/cnki_downloader/gui/viewmodels/search_vm.py src/cnki_downloader/gui/main_window.py
git commit -m "fix: add closeEvent and SearchViewModel.cancel() for worker cleanup on exit"
```

---

## Task 3: Add Signals to SearchView for Cross-View Communication

**Why:** SearchView currently reaches into `main_window._download_vm` and `main_window._switch_page()` (private members) to trigger downloads. MainWindow reaches into `search_view._table` (private widget) to handle double-clicks. Both violate MVVM encapsulation. The fix: SearchView emits signals, MainWindow connects to them.

**Files:**
- Modify: `src/cnki_downloader/gui/views/search_view.py:5,30-35,259-269` (add signals, refactor methods)
- Create: `tests/unit/test_search_view_signals.py`

- [ ] **Step 1: Write test for new signals**

```python
"""tests/unit/test_search_view_signals.py"""
import pytest

pytest.importorskip("PyQt6")

from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

from cnki_downloader.gui.views.search_view import SearchView


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _make_mock_vm():
    vm = MagicMock()
    vm.papers = []
    vm.is_loading = False
    return vm


def test_download_requested_signal_exists(qapp):
    """SearchView should have a download_requested signal."""
    view = SearchView(_make_mock_vm())
    assert hasattr(view, "download_requested")


def test_paper_double_clicked_signal_exists(qapp):
    """SearchView should have a paper_double_clicked signal."""
    view = SearchView(_make_mock_vm())
    assert hasattr(view, "paper_double_clicked")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_search_view_signals.py -v`
Expected: FAIL — signals don't exist yet

- [ ] **Step 3: Add signals to SearchView**

In `src/cnki_downloader/gui/views/search_view.py`:

1. Update the import on line 5:
```python
# BEFORE:
from PyQt6.QtCore import Qt
# AFTER:
from PyQt6.QtCore import Qt, pyqtSignal
```

2. Add signal declarations at the top of the `SearchView` class body (after the docstring, before `__init__`):
```python
class SearchView(QWidget):
    """搜索面板 — 关键词输入、高级搜索、结果表格（带勾选）"""

    download_requested = pyqtSignal(list)       # list[Paper]
    paper_double_clicked = pyqtSignal(object)   # Paper
```

- [ ] **Step 4: Refactor _on_download_selected to emit signal instead of accessing MainWindow**

```python
# BEFORE (line 259-269):
def _on_download_selected(self) -> None:
    """下载勾选的文献。"""
    papers = self.get_selected_papers()
    if not papers:
        QMessageBox.information(self, "提示", "请先勾选要下载的文献")
        return
    # 通过主窗口触发下载
    main_window = self.window()
    if hasattr(main_window, '_download_vm'):
        main_window._download_vm.download(papers)
        main_window._switch_page(1)

# AFTER:
def _on_download_selected(self) -> None:
    """下载勾选的文献。"""
    papers = self.get_selected_papers()
    if not papers:
        QMessageBox.information(self, "提示", "请先勾选要下载的文献")
        return
    self.download_requested.emit(papers)
```

- [ ] **Step 5: Add internal double-click handler and connect it**

Add this connection in `_init_ui`, right after the existing `self._table.itemChanged.connect(self._on_item_changed)` line:

```python
self._table.doubleClicked.connect(self._on_table_double_clicked)
```

Add this new method to SearchView:

```python
def _on_table_double_clicked(self, index) -> None:
    """Re-emit table double-click as a typed Paper signal."""
    row = index.row()
    papers = self._vm.papers
    if 0 <= row < len(papers):
        self.paper_double_clicked.emit(papers[row])
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/unit/test_search_view_signals.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/cnki_downloader/gui/views/search_view.py tests/unit/test_search_view_signals.py
git commit -m "refactor: add download_requested and paper_double_clicked signals to SearchView

SearchView now emits signals instead of reaching into MainWindow's
private members. This restores MVVM encapsulation boundaries."
```

---

## Task 4: Update MainWindow to Use SearchView Signals

**Why:** MainWindow currently accesses `self._search_view._table` to connect double-click. After Task 3, SearchView exposes proper signals. MainWindow connects to those instead. **Important:** This task MUST be committed together with or immediately after Task 3 — the old `_table.doubleClicked` connection must be replaced by the new signals.

**Files:**
- Modify: `src/cnki_downloader/gui/main_window.py:161-170` (`_connect_cross_view_signals` and `_on_paper_double_clicked`)

- [ ] **Step 1: Refactor _connect_cross_view_signals**

```python
# BEFORE (line 161-164):
def _connect_cross_view_signals(self) -> None:
    """连接跨视图交互：搜索结果中下载选中文献。"""
    # 在搜索页双击结果行时，跳转到下载
    self._search_view._table.doubleClicked.connect(self._on_paper_double_clicked)

# AFTER:
def _connect_cross_view_signals(self) -> None:
    """连接跨视图交互：搜索结果中下载选中文献。"""
    self._search_view.download_requested.connect(self._on_download_requested)
    self._search_view.paper_double_clicked.connect(self._on_paper_double_clicked)
```

- [ ] **Step 2: Add _on_download_requested handler and update _on_paper_double_clicked**

```python
def _on_download_requested(self, papers: list) -> None:
    """Handle download request from SearchView."""
    self._download_vm.download(papers)
    self._switch_page(1)

# BEFORE (line 166-170) — double-click downloads checked papers:
def _on_paper_double_clicked(self, index) -> None:
    papers = self._search_view.get_selected_papers()
    if papers:
        self._download_vm.download(papers)
        self._switch_page(1)

# AFTER — double-click downloads the specific paper that was double-clicked:
def _on_paper_double_clicked(self, paper) -> None:
    """Handle paper double-click: download that specific paper."""
    if paper:
        self._download_vm.download([paper])
        self._switch_page(1)
```

Note: The original `_on_paper_double_clicked` downloaded all *checked* papers, ignoring which row was double-clicked. The new version downloads the specific double-clicked paper, which is more intuitive UX. The "download checked papers" flow is handled by the download button → `download_requested` signal.

- [ ] **Step 3: Verify import works**

Run: `python -c "from cnki_downloader.gui.main_window import MainWindow; print('import OK')"`
Expected: `import OK`

- [ ] **Step 4: Commit**

```bash
git add src/cnki_downloader/gui/main_window.py
git commit -m "refactor: MainWindow connects to SearchView signals instead of private members

Completes the MVVM decoupling: MainWindow no longer accesses
SearchView._table directly. All cross-view communication goes
through typed pyqtSignal connections."
```

---

## Task 5: Final Verification & Cleanup

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run linter**

Run: `ruff check src/cnki_downloader/gui/`
Expected: No errors (fix any that appear)

- [ ] **Step 3: Verify no remaining private cross-access in SearchView**

Run: `grep -n "main_window\._\|self\.window()\._" src/cnki_downloader/gui/views/search_view.py`
Expected: No matches (SearchView no longer reaches into MainWindow)

- [ ] **Step 4: Verify MainWindow doesn't access SearchView._table**

Run: `grep -n "_search_view\._table" src/cnki_downloader/gui/main_window.py`
Expected: No matches

- [ ] **Step 5: Verify no module-level browser globals**

Run: `grep -n "^_browser\|^_context\|^_page" src/cnki_downloader/gui/workers/search_worker.py`
Expected: No matches

- [ ] **Step 6: Commit any cleanup**

```bash
git add -u
git commit -m "chore: final cleanup after GUI architecture fixes"
```
