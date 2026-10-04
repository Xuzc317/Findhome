#!/usr/bin/env python3
"""
HouseSearch Local v1 - 数据源验收记录

对每个数据源导出最近入库的真实房源记录（标题/价格/发布时间/source_url/抓取时间），
用于人工核对“与原页面是否一致”。

用法（项目根目录）:
    python verify_sources.py                      # 打印到终端
    python verify_sources.py --write docs/acceptance.md
    python verify_sources.py --min 5              # 少于 5 条视为不达标（默认）
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "houses.db")

# 判定“非真实链接”的特征（演示数据等）
FAKE_URL_MARKERS = ("demo.local", "example.com", "localhost")

SOURCE_NAMES = {
    "douban": "豆瓣",
    "beike": "贝壳",
    "xianyu": "闲鱼",
    "xiaohongshu": "小红书",
}


def fetch_rows(conn, source: str, limit: int):
    sql = """
        SELECT title, price, publish_time, last_active_time, source_url,
               crawl_time, source_id, district, rent_type, city,
               agent_score, ad_score, suspicious_score, confidence_score, raw_data
        FROM houses
        WHERE source = ?
        ORDER BY COALESCE(publish_time, last_active_time, crawl_time) DESC
        LIMIT ?
    """
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, (source, limit)).fetchall()]


def fmt(value) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def is_openable(url: str) -> bool:
    if not url:
        return False
    return not any(marker in url for marker in FAKE_URL_MARKERS)


def main():
    parser = argparse.ArgumentParser(description="数据源验收记录")
    parser.add_argument("--min", type=int, default=5, help="每个来源最少需要的条数")
    parser.add_argument("--limit", type=int, default=5, help="每个来源最多列出几条")
    parser.add_argument("--write", default="", help="同时写入指定 markdown 文件")
    parser.add_argument("--all", action="store_true", help="导出该来源的全部记录而非前 N 条")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库不存在: {DB_PATH}")
        return 1

    limit = 100000 if args.all else args.limit
    conn = sqlite3.connect(DB_PATH)

    lines = []
    lines.append(f"# 数据源验收记录（{datetime.now().strftime('%Y-%m-%d %H:%M')}）")
    lines.append("")
    lines.append("> 本文件由 `python verify_sources.py --write` 生成，仅包含真实采集数据；")
    lines.append("> 演示数据（demo.local 域名）会被标记为不可打开。")
    lines.append("")

    summary = []
    total_sources = 0
    passed_sources = 0

    for source, display in SOURCE_NAMES.items():
        rows = fetch_rows(conn, source, limit)
        real_rows = [r for r in rows if is_openable(r["source_url"])]
        total = conn.execute(
            "SELECT COUNT(*) FROM houses WHERE source = ?", (source,)
        ).fetchone()[0]

        total_sources += 1
        ok = len(real_rows) >= args.min
        if ok:
            passed_sources += 1

        print(f"\n{'=' * 78}")
        print(f"{'✅' if ok else '❌'} {display} ({source})  库存 {total} 条，"
              f"取最近 {len(rows)} 条，其中可打开链接 {len(real_rows)} 条 "
              f"(要求 ≥{args.min})")
        print("=" * 78)

        lines.append(f"## {display} ({source}) — {'✅ 达标' if ok else '❌ 未达标'}")
        lines.append("")
        lines.append(f"- 数据库总量：{total} 条")
        lines.append(f"- 最近记录：{len(rows)} 条，其中真实可打开链接 {len(real_rows)} 条")
        lines.append("")
        lines.append("| # | 标题 | 价格 | 发布时间 | 最近维护 | 抓取时间 | source_url | 风险(中/广/异) |")
        lines.append("|---|------|------|----------|----------|----------|------------|----------------|")

        for index, row in enumerate(rows, start=1):
            openable = is_openable(row["source_url"])
            url_text = row["source_url"] or "—"
            if not openable:
                url_text = f"⚠️(非真实) {url_text}"
            print(f"  {index}. [{fmt(row['price'])}元] {fmt(row['title'])[:44]}")
            print(f"     发布={fmt(row['publish_time'])} 维护={fmt(row['last_active_time'])} "
                  f"抓取={fmt(row['crawl_time'])[:19]}")
            print(f"     {url_text}")
            if not openable:
                print("     ⚠️ 该链接不是平台真实链接，不计入验收")

            lines.append(
                "| {i} | {title} | {price} | {pub} | {active} | {crawl} | {url} | {risk} |".format(
                    i=index,
                    title=(row["title"] or "").replace("|", "/")[:46],
                    price=fmt(row["price"]),
                    pub=fmt(row["publish_time"]),
                    active=fmt(row["last_active_time"]),
                    crawl=fmt(row["crawl_time"])[:19],
                    url=url_text,
                    risk=f"{fmt(row['agent_score'])}/{fmt(row['ad_score'])}/{fmt(row['suspicious_score'])}",
                )
            )

        lines.append("")

    print(f"\n{'=' * 78}")
    print(f"汇总: {passed_sources}/{total_sources} 个数据源达到 ≥{args.min} 条真实房源")
    print("=" * 78)
    lines.append(f"## 汇总\n\n{passed_sources}/{total_sources} 个数据源达到 ≥{args.min} 条真实房源\n")

    if args.write:
        out_path = args.write if os.path.isabs(args.write) else os.path.join(PROJECT_ROOT, args.write)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"📝 已写入: {out_path}")

    conn.close()
    return 0 if passed_sources == total_sources else 2


if __name__ == "__main__":
    sys.exit(main())
