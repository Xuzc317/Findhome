#!/usr/bin/env python3
"""
线上一致性校验：把库里的记录与平台当前页面逐一比对

回答验收问题："存放的数据与原页面是否一致？"

- 贝壳：重新抓取列表页，按房源编号（house_code）比对标题与价格
- 豆瓣：重新抓取帖子页，比对 h1 标题
- 平台风控拦截时会如实报告"无法比对"，不会假装通过

用法（项目根目录）:
    python verify_consistency.py                # 每个来源最多比对 5 条
    python verify_consistency.py --limit 10 --source beike
"""

import argparse
import asyncio
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bs4 import BeautifulSoup  # noqa: E402

from backend.crawlers.base import detect_block  # noqa: E402
from backend.crawlers.beike import BeikeCrawler  # noqa: E402
from backend.crawlers.douban import DoubanCrawler  # noqa: E402

DB_PATH = os.path.join(PROJECT_ROOT, "data", "houses.db")


def norm(text: str) -> str:
    """去掉空白后比对，避免页面排版差异造成假不一致"""
    return "".join((text or "").split())


async def check_beike(limit: int) -> dict:
    print("\n" + "=" * 74)
    print("【贝壳】重新抓取列表页，按房源编号比对标题与价格")
    print("=" * 74)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT city, source_id, title, price, source_url FROM houses "
        "WHERE source='beike' ORDER BY crawl_time DESC LIMIT ?", (limit,))]
    conn.close()

    if not rows:
        print("  ⚠️ 库中没有贝壳数据，跳过")
        return {"match": 0, "mismatch": 0, "unknown": 0}

    cities = sorted({r["city"] for r in rows if r["city"]})
    crawler = BeikeCrawler(cookie="")
    live = {}
    try:
        for city in cities:
            houses = await crawler.search(city=city, page=1)
            if not houses:
                print(f"  ⚠️ {city} 列表页无法获取: [{crawler.last_status}] {crawler.last_message}")
                continue
            for h in houses:
                if h.source_id:
                    live[h.source_id] = h
            print(f"  ℹ️ {city} 列表页解析到 {len(houses)} 条（用于比对）")
    finally:
        await crawler.close()

    match = mismatch = unknown = 0
    if not live:
        # 列表页完全取不到（被拦截/限流），不能把这种情况说成“未出现在当前页”
        print("  ⚠️ 列表页无法获取，本次无法比对（平台风控/限流）")
        print(f"     最后状态: [{crawler.last_status}] {crawler.last_message}")
        print(f"\n  结果: 一致 0 / 不一致 0 / 无法比对 {len(rows)}（列表页被拦截）")
        return {"match": 0, "mismatch": 0, "unknown": len(rows)}

    for row in rows:
        page = live.get(row["source_id"])
        if page is None:
            print(f"  ⚪ 当前页未出现（列表轮换）: {row['title'][:34]}")
            unknown += 1
            continue
        title_ok = norm(page.title) == norm(row["title"])
        price_ok = page.price == row["price"]
        if title_ok and price_ok:
            match += 1
            print(f"  ✅ {row['title'][:34]} | {row['price']}元 | 与页面一致")
        else:
            mismatch += 1
            print(f"  ❌ 不一致:")
            print(f"      库内: {row['title'][:40]} / {row['price']}")
            print(f"      线上: {page.title[:40]} / {page.price}")

    print(f"\n  结果: 一致 {match} / 不一致 {mismatch} / 未出现在当前页 {unknown}")
    return {"match": match, "mismatch": mismatch, "unknown": unknown}


async def check_douban(limit: int) -> dict:
    print("\n" + "=" * 74)
    print("【豆瓣】重新抓取帖子页，比对标题")
    print("=" * 74)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT title, price, source_url FROM houses "
        "WHERE source='douban' ORDER BY crawl_time DESC LIMIT ?", (limit,))]
    conn.close()

    if not rows:
        print("  ⚠️ 库中没有豆瓣数据，跳过")
        return {"match": 0, "mismatch": 0, "unknown": 0}

    crawler = DoubanCrawler(cookie="")
    match = mismatch = unknown = 0
    try:
        for row in rows:
            try:
                resp = await crawler.get(row["source_url"])
            except Exception as e:
                print(f"  ⚠️ 请求异常 {type(e).__name__}: {str(e)[:50]}")
                unknown += 1
                continue

            blocked = detect_block(resp.text)
            soup = BeautifulSoup(resp.text, "html.parser")
            h1 = soup.select_one("h1")
            live_title = h1.get_text(strip=True) if h1 else ""

            if blocked or not live_title:
                print(f"  ⚠️ 无法比对（{blocked or 'HTTP %s 无 h1' % resp.status_code}）: "
                      f"{row['title'][:30]}")
                unknown += 1
                continue

            if norm(live_title)[:18] == norm(row["title"])[:18]:
                match += 1
                print(f"  ✅ {row['title'][:34]} | 与页面一致")
            else:
                mismatch += 1
                print(f"  ❌ 不一致:\n      库内: {row['title'][:40]}\n      线上: {live_title[:40]}")
    finally:
        await crawler.close()

    print(f"\n  结果: 一致 {match} / 不一致 {mismatch} / 无法比对 {unknown}")
    return {"match": match, "mismatch": mismatch, "unknown": unknown}


async def main():
    parser = argparse.ArgumentParser(description="线上一致性校验")
    parser.add_argument("--limit", type=int, default=5, help="每个来源比对条数")
    parser.add_argument("--source", default="", help="只校验指定来源 (beike/douban)")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库不存在: {DB_PATH}")
        return 1

    results = {}
    if args.source in ("", "beike"):
        results["beike"] = await check_beike(args.limit)
    if args.source in ("", "douban"):
        results["douban"] = await check_douban(args.limit)

    print("\n" + "=" * 74)
    print("汇总")
    print("=" * 74)
    exit_code = 0
    for source, r in results.items():
        status = "✅ 一致" if r["mismatch"] == 0 and r["match"] > 0 else (
            "❌ 存在不一致" if r["mismatch"] else "⚠️ 无法比对（平台风控）")
        print(f"  {source:10} {status}  (一致 {r['match']} / 不一致 {r['mismatch']} / "
              f"无法比对 {r['unknown']})")
        if r["mismatch"]:
            exit_code = 2
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
