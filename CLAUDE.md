# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install in development mode (includes test dependencies)
pip install -e ".[dev]"

# Install with GUI support
pip install -e ".[gui]"

# Install everything
pip install -e ".[all,dev]"

# Run tests
pytest                          # all tests
pytest tests/unit/              # unit tests only
pytest tests/integration/       # integration tests only
pytest tests/unit/test_search.py::TestBuildSearchParams::test_basic_keyword  # single test

# Lint
ruff check                      # check for errors
ruff check --fix                # auto-fix

# Run the CLI
cnki search "关键词"
cnki download <url>
cnki convert <file.caj>
cnki auth login
cnki library list

# Run the GUI
cnki gui
cnki gui --theme dark

# Build executable
python scripts/build.py
```

## Architecture

Four-layer architecture where **core and services never depend on cli or gui**:

```
Presentation (cli/ + gui/)
    ↓
Services (services/)  — orchestration, coordinates core + database
    ↓
Core (core/)          — business logic: search, download, auth, convert, export
    ↓
Data (models/ + db/)  — dataclasses + SQLite repositories
```

### Key architectural patterns

- **Async-first**: All core/service/db code uses `async/await` (httpx, aiosqlite). GUI bridges via `QThread` + `asyncio.run()`. CLI calls `asyncio.run()` directly.
- **ProgressCallback Protocol** (`core/downloader.py`): UI-agnostic progress reporting. GUI implements it via Qt signals, CLI via Rich progress bars.
- **SessionManager** (`core/session.py`): Centralized httpx client with User-Agent rotation and randomized request delays to avoid CNKI anti-scraping.
- **Repository pattern** (`db/repository.py`): All DB access goes through typed repository classes, no raw SQL elsewhere.
- **MVVM for GUI**: ViewModels (`gui/viewmodels/`) use `pyqtSignal` for reactive updates. Workers (`gui/workers/`) run async code in separate QThreads.
- **Paper identity**: `dbname` + `filename` is the unique CNKI identifier (used for upsert in DB).

### Exception hierarchy

`CnkiError` (base) → `AuthError`, `SearchError`, `DownloadError`, `ConvertError`, `CaptchaRequiredError`, `CampusNetworkError`. Each carries a `user_hint` field for friendly messages.

## Configuration

Priority: environment variables > `~/.cnki_downloader/config.toml` > defaults. See `.env.example` for available env vars.

## Testing notes

- pytest-asyncio is set to `auto` mode — async test functions and fixtures work without `@pytest.mark.asyncio` decorators on the module level, but individual test methods still use the marker.
- Database tests use `tmp_path` fixture for isolated SQLite instances.
- GUI tests require `pip install -e ".[gui-test]"` (pytest-qt). GUI test dependencies are separated to avoid import errors in headless CI.
- `ruff` config: line length 100, target Python 3.10.
