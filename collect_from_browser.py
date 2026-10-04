#!/usr/bin/env python3
"""
通过常驻浏览器采集（闲鱼 / 小红书）

前提：先运行 `python browser_daemon.py` 打开浏览器并登录，且保持窗口不关。

为什么走浏览器：这两个平台的搜索接口要求页面 JS 生成的签名参数
（x-sign / x-s）。本项目不做签名逆向，而是用真实浏览器按正常用户方式
打开搜索页，页面自己完成签名，我们只读取渲染出来的结果。

用法:
    python collect_from_browser.py xianyu --station 清湖 --station 龙华
    python collect_from_browser.py xianyu --profile longhua      # 按需求档案里的站
    python collect_from_browser.py xianyu --profile longhua --suffix 租房 --suffix 单间
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import List, Optional

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.crawlers.base import RawHouse  # noqa: E402
from backend.crawlers.browser_fetch import (  # noqa: E402
    BrowserSession,
    search_goofish,
    search_xiaohongshu,
    xhs_is_listing,
)
from backend.services.condition import infer_rent_type  # noqa: E402

# 每个查询之间的礼貌间隔（秒）——不并发、不轰炸
QUERY_DELAY = 5.0


def cards_to_raw(cards, query_station: str, city: str = "深圳") -> List[RawHouse]:
    """把浏览器抓到的卡片转成统一 RawHouse"""
    results: List[RawHouse] = []
    for card in cards:
        price: Optional[int] = None
        if card.price_text:
            try:
                value = int(float(card.price_text.replace(",", "")))
                # 闲鱼上有把总价/押金写成价格的，超出合理月租范围就丢弃
                if 100 <= value <= 100000:
                    price = value
                else:
                    price = None
            except ValueError:
                price = None

        rent_type = infer_rent_type(card.title, card.raw_text)
        results.append(RawHouse(
            source="xianyu",
            source_id=card.item_id,
            source_url=card.url,
            title=card.title,
            description=card.raw_text,
            city=city,
            price=price,
            rent_type=rent_type,
            publish_time=None,          # 卡片上没有发布时间，不猜
            tags=[city, query_station, "闲鱼"],
            raw_data={"query": card.query, "station_hint": query_station},
        ))
    return results


async def collect_xianyu(stations: List[str], suffixes: List[str],
                         city: str = "深圳", cdp_port: int = 9222,
                         wait_ms: int = 8000) -> dict:
    from backend.crawlers.manager import CrawlerManager
    from backend.database import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    manager = CrawlerManager(db)

    total_cards = total_new = total_upd = 0
    per_station = []
    try:
        async with BrowserSession(cdp_port=cdp_port) as session:
            for station in stations:
                station_new = station_cards = 0
                for suffix in suffixes:
                    query = f"{station} {suffix}"
                    try:
                        cards = await search_goofish(session, query, wait_ms=wait_ms)
                    except Exception as e:
                        print(f"  ❌ {query}: {type(e).__name__}: {str(e)[:70]}", flush=True)
                        continue

                    station_cards += len(cards)
                    total_cards += len(cards)
                    if cards:
                        raw = cards_to_raw(cards, station, city=city)
                        inserted, updated = manager._process_houses(raw, "xianyu")
                        station_new += inserted
                        total_new += inserted
                        total_upd += updated
                        print(f"  ✅ {query:16} 抓到 {len(cards):3} 条 → 新增 {inserted:3} 更新 {updated:3}",
                              flush=True)
                    else:
                        print(f"  ⚪ {query:16} 0 条", flush=True)
                    await asyncio.sleep(QUERY_DELAY)
                per_station.append({"station": station, "cards": station_cards,
                                    "new": station_new})
    finally:
        db.close()

    return {"cards": total_cards, "new": total_new, "updated": total_upd,
            "perStation": per_station}


async def collect_xiaohongshu(stations: List[str], suffixes: List[str],
                              city: str = "深圳", cdp_port: int = 9222,
                              wait_ms: int = 9000) -> dict:
    """采集小红书笔记（只保留"出租房源"类，排除求租/吐槽/攻略）"""
    from backend.crawlers.manager import CrawlerManager
    from backend.database import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    manager = CrawlerManager(db)

    total_cards = total_kept = total_new = 0
    per_station = []
    try:
        async with BrowserSession(cdp_port=cdp_port) as session:
            for station in stations:
                kept = station_new = cards_n = 0
                for suffix in suffixes:
                    query = f"{station} {suffix}"
                    try:
                        cards = await search_xiaohongshu(session, query, wait_ms=wait_ms)
                    except Exception as e:
                        print(f"  ❌ {query}: {type(e).__name__}: {str(e)[:70]}", flush=True)
                        continue
                    cards_n += len(cards)
                    total_cards += len(cards)

                    raw = []
                    for card in cards:
                        title = card.get("title") or ""
                        if not xhs_is_listing(title, card.get("text") or ""):
                            continue
                        import re as _re
                        m = _re.search(r"/explore/([0-9a-f]+)", card.get("href") or "")
                        note_id = m.group(1) if m else ""
                        if not note_id:
                            continue
                        from backend.crawlers.base import RawHouse as _RH
                        from backend.services.condition import infer_rent_type as _irt
                        from backend.crawlers.base import extract_price as _ep
                        text = card.get("text") or title
                        raw.append(_RH(
                            source="xiaohongshu",
                            source_id=note_id,
                            source_url=f"https://www.xiaohongshu.com/explore/{note_id}",
                            title=title[:200],
                            description=text[:500],
                            city=city,
                            price=_ep(title) or _ep(text),
                            rent_type=_irt(title, text),
                            publish_time=None,
                            publisher=(card.get("author") or "").split("\n")[0] or None,
                            tags=[city, station, "小红书"],
                            raw_data={"query": query, "station_hint": station},
                        ))

                    kept += len(raw)
                    total_kept += len(raw)
                    if raw:
                        inserted, updated = manager._process_houses(raw, "xiaohongshu")
                        station_new += inserted
                        total_new += inserted
                        print(f"  ✅ {query:16} 笔记 {len(cards):3} → 房源类 {len(raw):2} → 新增 {inserted:2}",
                              flush=True)
                    else:
                        print(f"  ⚪ {query:16} 笔记 {len(cards):3} → 无房源类", flush=True)
                    await asyncio.sleep(QUERY_DELAY)
                per_station.append({"station": station, "cards": cards_n,
                                    "kept": kept, "new": station_new})
    finally:
        db.close()

    return {"cards": total_cards, "kept": total_kept, "new": total_new,
            "perStation": per_station}


def main() -> int:
    parser = argparse.ArgumentParser(description="通过常驻浏览器采集闲鱼/小红书")
    parser.add_argument("platform", choices=["xianyu", "xiaohongshu"],
                        default="xianyu", nargs="?", help="采集哪个平台")
    parser.add_argument("--station", action="append", default=[],
                        help="地铁站名，可重复；不传则用 --profile 里的站点")
    parser.add_argument("--profile", default="", help="需求档案名（取其站点清单）")
    parser.add_argument("--suffix", action="append", default=[],
                        help="查询后缀，默认 租房 / 单间 / 一房一厅")
    parser.add_argument("--city", default="深圳")
    parser.add_argument("--port", type=int, default=9222, help="浏览器调试端口")
    parser.add_argument("--wait-ms", type=int, default=8000, help="每页等待渲染毫秒")
    args = parser.parse_args()

    stations = list(args.station)
    if not stations and args.profile:
        from backend.services.match import Profile
        stations = Profile.load(args.profile).stations
    if not stations:
        print("❌ 请用 --station 指定站点，或用 --profile 指定需求档案")
        return 1

    suffixes = args.suffix or ["租房", "单间", "一房一厅"]

    print("=" * 74)
    print(f"通过常驻浏览器采集闲鱼：{len(stations)} 个站 × {len(suffixes)} 个查询")
    print(f"站点：{'、'.join(stations)}")
    print("=" * 74, flush=True)

    if args.platform == "xianyu":
        result = asyncio.run(collect_xianyu(stations, suffixes, city=args.city,
                                            cdp_port=args.port, wait_ms=args.wait_ms))
    else:
        result = asyncio.run(collect_xiaohongshu(stations, suffixes, city=args.city,
                                                 cdp_port=args.port, wait_ms=args.wait_ms))

    print("\n" + "=" * 74)
    print(f"完成：共抓取 {result['cards']} 张卡片 → 新增 {result['new']} 条"
          + (f"，更新 {result['updated']} 条" if 'updated' in result else "")
          + (f"，其中房源类 {result.get('kept', 0)} 条" if 'kept' in result else ""))
    print("=" * 74)
    for item in result["perStation"]:
        print(f"  {item['station']:8} 卡片 {item['cards']:4} → 新增 {item['new']:3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
