"""快速搜索测试脚本"""
import asyncio
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from cnki_downloader.core.session import SessionManager
from cnki_downloader.core.search import search
from cnki_downloader.models.search_result import SearchQuery


async def main():
    async with SessionManager() as sm:
        q = SearchQuery(
            keyword="组织绩效",
            source_types="CJFQ",
            language="zh",
            page_size=20,
        )
        result = await search(sm, q)
        print(f"总结果数: {result.total_count}")
        for i, p in enumerate(result.papers[:2], 1):
            print(f"\n--- 文献 {i} ---")
            print(f"标题: {p.title}")
            print(f"作者: {', '.join(p.authors)}")
            print(f"期刊: {p.journal}")
            print(f"日期: {p.publish_date}")
            print(f"类型: {p.doc_type}")
            print(f"URL: {p.url}")


if __name__ == "__main__":
    asyncio.run(main())
