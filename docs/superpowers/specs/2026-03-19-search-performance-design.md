# Search Performance Optimization Design

## Goal

Reduce GUI search latency by (A) keeping the Playwright browser alive across searches via a dedicated event loop thread, and (B) replacing fixed `asyncio.sleep()` calls with smart waits on actual page content.

## Current State

Each search creates a new Playwright browser, uses it, and closes it. Two fixed `asyncio.sleep(3)` calls add 3-6 seconds per search. Total latency: ~8 seconds per search regardless of whether it's the first or tenth.

## Design

### Component: BrowserThread

A new `QThread` subclass that runs a persistent `asyncio` event loop. The browser is launched on first use and reused for all subsequent searches.

**File:** `src/cnki_downloader/gui/workers/browser_thread.py`

**Interface:**

```python
class BrowserThread(QThread):
    """Persistent asyncio event loop thread with reusable Playwright browser."""

    def run(self):
        """Start the event loop (runs forever until shutdown)."""

    def submit(self, coro) -> concurrent.futures.Future:
        """Submit a coroutine to the event loop from any thread. Returns a Future."""

    def shutdown(self):
        """Close browser and stop event loop. Called from MainWindow.closeEvent."""
```

**Lifecycle:**
- Created and started once by `SearchViewModel.__init__`
- `submit()` is thread-safe (uses `asyncio.run_coroutine_threadsafe`)
- Browser launched lazily on first `submit()` that needs it
- `shutdown()` called from `MainWindow.closeEvent` → `SearchViewModel.cancel()`

### Changes to SearchWorker

SearchWorker stops being a QThread. It becomes a plain class that submits search coroutines to BrowserThread via `submit()`. The search coroutine uses the shared browser/page instead of creating its own.

Alternatively (simpler): SearchWorker remains a QThread but receives the event loop from BrowserThread and submits work to it instead of calling `asyncio.run()`.

**Chosen approach:** SearchWorker is removed. SearchViewModel directly submits `_search()` as a coroutine to BrowserThread, receives results via a callback that emits signals.

**Flow:**
```
User clicks search
  → SearchViewModel.search()
    → BrowserThread.submit(_search(query))
      → _search() runs on persistent event loop, reuses browser
      → Future.add_done_callback() → emit results_changed signal
```

### Smart Waits (Part B)

Replace fixed sleeps with content-aware waits:

| Current | Replacement |
|---------|-------------|
| `await asyncio.sleep(3)` after `page.goto()` | `await page.wait_for_selector("table.result-table-list", timeout=10000)` |
| `await asyncio.sleep(3)` after pagination click | `await page.wait_for_function("...", timeout=8000)` or `wait_for_load_state("networkidle")` |

Fallback: if `wait_for_selector` times out, proceed anyway (current behavior with sleep also has no guarantee).

### Changes to SearchViewModel

- Owns a `BrowserThread` instance (created in `__init__`, started immediately)
- `search()` submits coroutine to BrowserThread instead of creating SearchWorker
- `cancel()` calls `BrowserThread.shutdown()` for app exit

### Changes to MainWindow

- `closeEvent` already calls `search_vm.cancel()` — no changes needed if `cancel()` handles BrowserThread shutdown.

## Error Handling

- If browser crashes mid-search, catch the error, set `_browser = None`, and retry once (auto-relaunch)
- Cookie loading failures are already handled (silent fallback)
- Captcha detection remains the same

## Testing

- Unit test: verify BrowserThread starts/stops cleanly
- Unit test: verify submit() returns results
- Unit test: verify no module-level globals remain
- Existing tests remain unchanged

## Expected Performance

| Scenario | Before | After |
|----------|--------|-------|
| First search | ~8s | ~5s (browser launch + smart wait) |
| Subsequent search | ~8s | ~2s (reuse browser + smart wait) |
| Pagination | ~6s | ~2s (reuse browser + smart wait) |
