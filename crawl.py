#!/usr/bin/env python3
"""
HouseSearch 爬虫 CLI 工具
手动触发各平台数据采集

用法（必须在项目根目录执行）:
    python crawl.py health
    python crawl.py douban --city 北京 --pages 3
    python crawl.py beike --city 深圳 --keyword 南山
    python crawl.py all --city 上海
"""

import argparse
import asyncio
import os
import sys

# 确保项目根目录在 sys.path 中，从而可以统一使用 backend.* 绝对导入
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.crawlers.manager import CrawlerManager  # noqa: E402
from backend.database import SessionLocal, init_db  # noqa: E402


async def crawl_source(source: str, city: str, keyword: str, pages: int):
    """采集单个数据源"""
    db = SessionLocal()
    try:
        manager = CrawlerManager(db)
        result = await manager.crawl(source, city, keyword, pages)

        if result["success"]:
            print(f"✅ {source} 采集完成: {result['count']} 条房源")
        else:
            print(f"❌ {source} 采集失败: {result['message']}")

        return result
    finally:
        db.close()


async def check_health():
    """检查所有数据源健康状态"""
    db = SessionLocal()
    try:
        manager = CrawlerManager(db)
        results = await manager.check_all_health()

        print("\n📊 数据源健康检查:")
        print("-" * 50)
        for r in results:
            status_icon = "🟢" if r.get("status") == "ok" else "🔴"
            login_icon = "🔐" if r.get("needs_login") else ""
            print(f"{status_icon} {r['display_name']} ({r['source']}) {login_icon}")
            print(f"   状态: {r.get('status')} | {r.get('message', '')}")
        print("-" * 50)

        return results
    finally:
        db.close()


async def main():
    parser = argparse.ArgumentParser(description="HouseSearch 爬虫工具")
    parser.add_argument("source", choices=["douban", "beike", "xianyu", "xiaohongshu", "all", "health"],
                        help="数据源名称")
    parser.add_argument("--city", default="上海", help="目标城市")
    parser.add_argument("--keyword", default="", help="搜索关键词")
    parser.add_argument("--pages", type=int, default=1, help="采集页数")

    args = parser.parse_args()

    # 初始化数据库
    init_db()

    if args.source == "health":
        await check_health()
        return

    if args.source == "all":
        sources = ["douban", "beike", "xianyu", "xiaohongshu"]
        for source in sources:
            print(f"\n🚀 开始采集: {source}")
            await crawl_source(source, args.city, args.keyword, args.pages)
    else:
        await crawl_source(args.source, args.city, args.keyword, args.pages)


if __name__ == "__main__":
    asyncio.run(main())
