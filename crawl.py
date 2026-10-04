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


def run_metro(city: str, sync: bool, overwrite: bool):
    """导入地铁静态数据，可选再用高德 POI 校准坐标"""
    from backend.database import SessionLocal
    from backend.services import metro as metro_service
    from backend.services.amap import AmapClient

    db = SessionLocal()
    try:
        before = metro_service.metro_stats(db, city)
        stats = metro_service.import_static(db, city)
        if stats.lines == 0 and before["lines"] > 0:
            print(f"📥 静态数据已导入过（{before['lines']} 条线路 / "
                  f"{before['stations']} 个站点），本次未新增")
        else:
            print(f"📥 {stats.message}")
        if stats.stations == 0 and "不存在" in stats.message:
            print(f"   请把地铁数据放到 data/metro/ 下（支持 {city}.json 或拼音文件名）")

        if sync:
            amap = AmapClient()
            if not amap.available:
                print("⚠️  未配置 AMAP_WEB_KEY，跳过坐标校准（站点仍用静态坐标）")
            else:
                result = metro_service.refresh_from_amap_poi(
                    db, city, amap, overwrite=overwrite)
                print(f"🛰️  {result.get('message')}")
                for err in (result.get("errors") or [])[:3]:
                    print(f"   ⚠️ {err}")
                amap.close()

        info = metro_service.metro_stats(db, city)
        print(f"📊 {city} 地铁：{info['lines']} 条线路 / {info['stations']} 个站点 / "
              f"有坐标 {info['stationsWithCoord']}")
        if info["stationsWithCoord"] < info["stations"]:
            print("   提示：部分站点缺坐标，无法计算到这些站的步行距离")
    finally:
        db.close()


def run_locate(city: str, limit: int, use_llm: bool, only_missing: bool):
    """批量推断房源坐标（小批量、可反复运行增量推进）"""
    from backend.database import SessionLocal
    from backend.services import geolocate
    from backend.services.amap import AmapClient
    from backend.services.llm import LLMClient

    db = SessionLocal()
    amap = AmapClient()
    llm = LLMClient()
    try:
        if not amap.available:
            print("❌ 未配置 AMAP_WEB_KEY，无法定位。"
                  "请在 https://console.amap.com 创建「Web服务」类型 Key 填入 .env")
            return

        llm_extract = None
        if use_llm and llm.available:
            def llm_extract(house):  # noqa: E306
                text = " ".join(filter(None, [house.title, house.description, house.tags]))
                return llm.extract_location(text, city=house.city or city)
            print(f"🤖 大模型: {llm.provider}（未配置时自动降级为规则解析）")
        elif use_llm:
            print("ℹ️  大模型未配置，仅用规则解析")

        result = geolocate.locate_batch(
            db, amap, city=city, limit=limit,
            only_missing=only_missing, llm_extract=llm_extract)

        print(f"\n📍 处理 {result['total']} 条 | 成功 {result['located']} | "
              f"失败 {result['failed']} | 跳过 {result['skipped']}")
        print(f"   高德调用 {result['amapCalls']} 次（缓存命中 {result['cacheHits']}）")
        for item in result["details"][:10]:
            precision = item.get("precision") or "-"
            print(f"   [{precision}] {str(item.get('title'))[:24]:26} {item['result'][:50]}")
        if result["failed"]:
            print("   注：只匹配到区县级的房源坐标会留空（不在地图上放近似点）")
    finally:
        llm.close()
        amap.close()
        db.close()


def run_distance(city: str, station_name: str, limit: int, max_calls: int,
                 only_missing: bool):
    """计算房源到指定地铁站的真实步行距离"""
    from backend.database import SessionLocal
    from backend.services import metro as metro_service
    from backend.services import station_distance
    from backend.services.amap import AmapClient

    db = SessionLocal()
    amap = AmapClient()
    try:
        metro_service.ensure_seeded(db, city)
        station = metro_service.get_station(db, city, station_name)
        if station is None:
            print(f"❌ 未找到站点「{station_name}」（城市 {city}）。"
                  f"可用 python crawl.py metro --city {city} 导入数据后重试")
            return
        if station.lng is None or station.lat is None:
            print(f"❌ 站点「{station.name}」缺坐标，无法计算。"
                  f"先执行 python crawl.py metro --city {city} --sync")
            return

        if not amap.available:
            print("❌ 未配置 AMAP_WEB_KEY，无法计算步行距离")
            return

        result = station_distance.compute_for_station(
            db, station, amap, city=city, limit=limit,
            only_missing=only_missing, max_amap_calls=max_calls)

        print(f"\n🚇 {station.name}（{station.lng:.5f},{station.lat:.5f}，"
              f"坐标来源 {station.coord_source}）")
        print(f"   {result.get('message')}")
        coverage = station_distance.station_coverage(db, station.id)
        print(f"   覆盖: 已算 {coverage['ok']} 条"
              + (f"，{coverage['noRoute']} 条无法步行到达" if coverage["noRoute"] else ""))
        if result.get("skipped"):
            print("   提示：超出 3km 直线预筛范围的房源不参与计算（现实中已不属地铁房）")
    finally:
        amap.close()
        db.close()


async def main():
    parser = argparse.ArgumentParser(description="Findhome 采集与地理工具")
    parser.add_argument("source",
                        choices=["douban", "beike", "xianyu", "xiaohongshu",
                                 "all", "health", "metro", "locate", "distance"],
                        help="数据源名称，或 metro/locate/distance 工具")
    parser.add_argument("--city", default=None,
                        help="目标城市（采集默认北京；metro/locate/distance 默认深圳）")
    parser.add_argument("--keyword", default="", help="搜索关键词")
    parser.add_argument("--pages", type=int, default=1, help="采集页数")
    parser.add_argument("--rent-type", type=int, default=0,
                        help="[贝壳] 0全部 1合租 3整租")
    parser.add_argument("--with-detail", type=int, default=0,
                        help="为前 N 条抓取详情补全正文/图片（受平台风控限制，默认 0）")
    parser.add_argument("--group", action="append", default=[],
                        help="[豆瓣] 指定小组 ID，可重复传入以覆盖内置映射")
    # metro / locate / distance 相关
    parser.add_argument("--sync", action="store_true",
                        help="[metro] 用高德 POI 校准站点坐标")
    parser.add_argument("--overwrite", action="store_true",
                        help="[metro] 覆盖已有坐标")
    parser.add_argument("--limit", type=int, default=10,
                        help="[locate/distance] 本次处理条数")
    parser.add_argument("--max-calls", type=int, default=400,
                        help="[distance] 本次高德调用上限（配额保护）")
    parser.add_argument("--no-llm", action="store_true",
                        help="[locate] 只用规则解析，不调用大模型")
    parser.add_argument("--all-houses", action="store_true",
                        help="[locate/distance] 包含已处理过的房源，重算一遍")
    parser.add_argument("--station", default="", help="[distance] 地铁站名，如 车公庙")

    args = parser.parse_args()

    init_db()

    if args.source == "metro":
        run_metro(args.city or "深圳", args.sync, args.overwrite)
        return

    if args.source == "locate":
        run_locate(args.city or "深圳", args.limit,
                   use_llm=not args.no_llm,
                   only_missing=not args.all_houses)
        return

    if args.source == "distance":
        if not args.station:
            print("❌ 请用 --station 指定站点名，例如：python crawl.py distance --station 车公庙")
            return
        run_distance(args.city or "深圳", args.station, args.limit,
                     args.max_calls, only_missing=not args.all_houses)
        return

    if args.source == "health":
        await check_health()
        return

    city = args.city or "北京"
    sources = ["douban", "beike", "xianyu", "xiaohongshu"] if args.source == "all" else [args.source]
    for source in sources:
        if len(sources) > 1:
            print(f"\n🚀 开始采集: {source}")
        await crawl_source(source, city, args.keyword, args.pages,
                           args.rent_type, args.with_detail, args.group)


if __name__ == "__main__":
    asyncio.run(main())
