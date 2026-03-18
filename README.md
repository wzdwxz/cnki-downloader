# CNKI 文献下载器

一个集搜索、下载、格式转换、文献管理于一体的知网(CNKI)文献下载工具，提供 GUI 和 CLI 两种使用方式。

## 功能特性

- **文献搜索** — 关键词、作者、期刊、日期范围等多条件检索
- **文献下载** — 单篇/批量下载，支持断点续传和并发控制
- **格式转换** — CAJ 自动转 PDF（基于 caj2pdf / PyMuPDF）
- **文献管理** — 收藏、分类目录、标签系统、本地搜索
- **引用导出** — BibTeX、EndNote (.enw)、GB/T 7714-2015
- **双接口** — PyQt6 图形界面 + Typer 命令行
- **双认证** — 校园网直连 / 个人账号登录

## 安装

需要 Python 3.10+。

```bash
# 仅 CLI
pip install -e .

# CLI + GUI
pip install -e ".[gui]"

# 全部功能（含 CAJ 转换）
pip install -e ".[all]"
```

## 快速开始

### 命令行

```bash
# 搜索文献
cnki search "深度学习" --author "张三" --journal "计算机学报"

# 下载文献（指定搜索结果序号）
cnki download "深度学习" --index 1

# 批量下载
cnki download "机器学习" --batch --concurrent 3

# CAJ 转 PDF
cnki convert paper.caj

# 登录账号
cnki auth login -u your_username

# 查看网络/登录状态
cnki auth status

# 管理文献库
cnki library list
cnki library export --format bibtex --output refs.bib
```

### 图形界面

```bash
cnki gui              # 默认亮色主题
cnki gui --theme dark  # 暗色主题
```

GUI 提供搜索、下载管理、文献库、设置四个功能面板，支持亮/暗主题切换。

## 配置

配置文件位于 `~/.cnki_downloader/config.toml`，也可通过环境变量覆盖：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `CNKI_DOWNLOAD_DIR` | 下载目录 | `~/Downloads/cnki` |
| `CNKI_USERNAME` | 知网账号 | — |
| `CNKI_PASSWORD` | 知网密码 | — |
| `CNKI_LOG_LEVEL` | 日志级别 | `INFO` |

## 开发

```bash
# 安装开发依赖
pip install -e ".[all,dev]"

# 运行测试
pytest

# 代码检查
ruff check

# 构建可执行文件
python scripts/build.py
```

## 技术栈

| 类别 | 选型 |
|------|------|
| HTTP 客户端 | httpx (HTTP/2, async) |
| HTML 解析 | BeautifulSoup4 + lxml |
| 数据库 | SQLite (aiosqlite, WAL 模式) |
| GUI | PyQt6 (MVVM 模式) |
| CLI | Typer + Rich |
| CAJ 转换 | caj2pdf / PyMuPDF |
| 凭证存储 | keyring |
| 打包 | PyInstaller |

## 项目架构

```
Presentation (cli/ + gui/)     ← 可替换的薄壳
       ↓
Services (services/)           ← 编排层
       ↓
Core (core/)                   ← 核心业务逻辑
       ↓
Data (models/ + db/)           ← 数据模型 + SQLite 持久化
```

核心原则：core 层和 services 层完全不依赖 gui 或 cli。

## 许可证

MIT
