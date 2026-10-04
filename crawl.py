#!/usr/bin/env python3
"""
HouseSearch 爬虫 CLI 工具
手动触发各平台数据采集

用法（必须在项目根目录执行）:
    python crawl.py health
    python crawl.py douban --city 北京 --pages 1 [--with-detail 5]
    python crawl.py beike --city 深圳 [--rent-type 1|3]
    python crawl.py xianyu --city 上海
    python crawl.py xiaohongshu --city 上海
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

from backend.crawlers.base import (  # noqa: E402
    STATUS_BLOCKED,
    STATUS_NEEDS_LOGIN,
    STATUS_OK,
)
from backend.crawlers.manager import CrawlerManager  # noqa: E402
from backend.database import SessionLocal, init_db  # noqa: E402

STATUS_ICON = {
    "ok": "✅",
    "empty": "⚪",
    "needs_login": "🔐",
    "blocked": "🚫",
    "unavailable": "❌",
    "error": "💥",
}


async def crawl_source(source, city, keyword, pages, rent_type, with_detail, groups):
    """采集单个数据源"""
    db = SessionLocal()
    try:
        manager = CrawlerManager(db)
        crawler_kwargs = {}
        if source == "douban" and groups:
            crawler_kwargs["groups"] = groups

        if crawler_kwargs:
            # 需要自定义参数时走临时实例
            crawler_class = manager.CRAWLERS[source]
            cookie = getattr(manager.settings, f"{source}_cookie", "") or ""
            original = manager.get_crawler

            def patched(src, **kw):
                if src == source:
                    return crawler_class(cookie=cookie, **crawler_kwargs)
                return original(src, **kw)

            manager.get_crawler = patched

        result = await manager.crawl(
            source, city, keyword, pages,
            rent_type=rent_type, with_detail=with_detail,
        )

        icon = STATUS_ICON.get(result.get("status"), "❔")
        print(f"{icon} {source} [{result.get('status')}] {result.get('message')}")
        if result.get("total"):
            print(f"   解析 {result['total']} 条 → 新增 {result['count']} 条，更新 {result['updated']} 条")
        return result
    finally:
        db.close()


async def check_health():
    """检查所有数据源健康状态"""
    db = SessionLocal()
    try:
        manager = CrawlerManager(db)
        results = await manager.check_all_health()

        print("\n📊 数据源健康检查（真实请求 + 真实解析）")
        print("=" * 78)
        for r in results:
            icon = STATUS_ICON.get(r.get("status"), "❔")
            login = "🔐需登录" if r.get("needs_login") else "公开"
            cookie = "已配置Cookie" if r.get("cookie_configured") else "无Cookie"
            print(f"{icon} {r['display_name']} ({r['source']})  [{login} / {cookie}]")
            print(f"   状态: {r.get('status')} | 已验证: {r.get('verified')}")
            print(f"   说明: {r.get('message', '')}")
            if not r.get("detail_available"):
                print(f"   详情: 不可用 —— {r.get('detail_unavailable_reason', '')}")
        print("=" * 78)
        return results
    finally:
        db.close()


async def main():
    parser = argparse.ArgumentParser(description="HouseSearch 爬虫工具")
    parser.add_argument("source",
                        choices=["douban", "beike", "xianyu", "xiaohongshu", "all", "health"],
                        help="数据源名称")
    parser.add_argument("--city", default="北京", help="目标城市")
    parser.add_argument("--keyword", default="", help="搜索关键词")
    parser.add_argument("--pages", type=int, default=1, help="采集页数")
    parser.add_argument("--rent-type", type=int, default=0,
                        help="[贝壳] 0全部 1合租 3整租")
    parser.add_argument("--with-detail", type=int, default=0,
                        help="为前 N 条抓取详情补全正文/图片（受平台风控限制，默认 0）")
    parser.add_argument("--group", action="append", default=[],
                        help="[豆瓣] 指定小组 ID，可重复传入以覆盖内置映射")

    args = parser.parse_args()

    init_db()

    if args.source == "health":
        await check_health()
        return

    sources = ["douban", "beike", "xianyu", "xiaohongshu"] if args.source == "all" else [args.source]
    for source in sources:
        if len(sources) > 1:
            print(f"\n🚀 开始采集: {source}")
        await crawl_source(source, args.city, args.keyword, args.pages,
                           args.rent_type, args.with_detail, args.group)


if __name__ == "__main__":
    asyncio.run(main())
