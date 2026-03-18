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

# 全部功能（含 CAJ 转换 + 浏览器自动化）
pip install -e ".[all]"

# 仅浏览器自动化
pip install -e ".[browser]"
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

# 退出登录
cnki auth logout

# 删除保存的凭证
cnki auth forget

# 管理文献库
cnki library list
cnki library export --format bibtex --output refs.bib

# 标签管理
cnki library tag add <paper_id> "标签名"
cnki library tag list

# 分类管理
cnki library category create "分类名"
cnki library category list
```

### 图形界面

```bash
cnki gui              # 默认亮色主题
cnki gui --theme dark  # 暗色主题
```

GUI 提供搜索、下载管理、文献库、设置四个功能面板，支持亮/暗主题切换。

### 浏览器自动化批量搜索

使用 Playwright 驱动真实浏览器，自动完成多主题批量搜索与下载。首次运行需在浏览器中手动完成验证（如有），之后 Cookie 自动保存，后续运行无需重复验证。

```bash
# 安装 Playwright
pip install playwright && python -m playwright install chromium

# 基本用法（使用脚本内预定义的搜索任务）
python scripts/cnki_browser_search.py

# 指定下载目录
python scripts/cnki_browser_search.py --output D:/papers

# 限制每个主题最多搜集 50 篇
python scripts/cnki_browser_search.py --max 50

# 组合使用
python scripts/cnki_browser_search.py --max 30 --output D:/papers
```

在脚本的 `TASKS` 列表中定义搜索任务，每个任务支持以下参数：

```python
SearchTask(
    name="组织承诺+公务员+公平(仅期刊)",
    keywords=["组织承诺", "公务员", "公平"],   # 多关键词 AND 搜索
    start_year=2020,
    end_year=2025,
    source_types=["期刊"],                     # 文献类型过滤（见下表）
    max_papers=50,                             # 本任务最大数量（0=不限）
)
```

**文献类型 (`source_types`)：**

| 值 | 说明 |
|---|------|
| `"期刊"` | 学术期刊 (CJFQ) |
| `"博士"` | 博士学位论文 (CDFD) |
| `"硕士"` | 硕士学位论文 (CMFD) |
| `"学位论文"` | 博士 + 硕士 |
| `"会议"` | 会议论文 (CPFD) |
| `"报纸"` | 报纸 (CCND) |
| `"图书"` | 图书 (CRLD) |
| `"年鉴"` | 年鉴 (CYFD) |
| `"标准"` | 标准 (SCSF) |
| `"专利"` | 专利 (SCOD) |
| `"成果"` | 科技成果 (SNAD) |
| `"学术辑刊"` | 学术辑刊 (CCJD) |

可组合使用，如 `source_types=["期刊", "会议"]`。留空 `[]` 表示不限类型。

**数量限制：**
- `--max N`：全局默认上限，对所有任务生效
- `max_papers=N`：单任务上限，覆盖全局值
- 若知网实际结果少于上限，返回全部可获取的结果（不报错）

**Cookie 持久化：**
- Cookie 自动保存到 `~/.cnki_downloader/browser_state.json`（Windows 为 `%APPDATA%/cnki_downloader/`）
- 再次运行时自动加载，Cookie 有效则全程后台运行（无头模式）
- Cookie 失效时自动切换到有头模式，让用户重新验证

## 配置

配置文件位于 `~/.cnki_downloader/config.toml`（Windows 为 `%APPDATA%/cnki_downloader/config.toml`），也可通过环境变量覆盖：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `CNKI_DOWNLOAD_DIR` | 下载目录 | `~/Downloads/cnki` |
| `CNKI_USERNAME` | 知网账号 | — |
| `CNKI_PASSWORD` | 知网密码 | — |
| `CNKI_LOG_LEVEL` | 日志级别 | `INFO` |

下载路径优先级：命令行 `--output` > 环境变量 > TOML 配置文件 > GUI 设置面板 > 默认值。

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
| 浏览器自动化 | Playwright (Chromium) |
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
