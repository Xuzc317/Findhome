"""按需采集任务：启动 → 实时到各平台搜索 → 入库 → 定位 → 算距离 → 筛选

为什么需要任务化：
用户点"开始搜索"后要真的去各平台抓，这一步是**分钟级**的
（闲鱼 12 个关键词 ≈ 3-5 分钟，还要定位与步行距离计算）。
HTTP 请求不能挂这么久——浏览器会超时、也没有进度可看。
所以拆成：POST 启动任务拿 taskId → 前端轮询进度 → 完成后取结果。

执行方式：任务跑在**同一个事件循环**里（`asyncio.create_task`）。
采集本身是 async（Playwright），会自然让出控制权；
定位/距离计算是同步阻塞的（httpx / 高德 SDK），统一丢进线程池，
避免把事件循环卡死导致进度接口也没法响应。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

# 任务状态
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

# 阶段（前端据此显示"正在做什么"）
STAGES = [
    ("checking", "检查平台登录状态"),
    ("collecting", "到各平台搜索房源"),
    ("locating", "推断房源位置"),
    ("distance", "计算真实步行距离"),
    ("matching", "按条件筛选"),
    ("done", "完成"),
]

_TASKS: Dict[str, "CollectTask"] = {}
# 保留最近任务数量，避免内存无限增长
MAX_TASKS = 30


@dataclass
class CollectTask:
    id: str
    criteria: dict
    status: str = STATUS_PENDING
    stage: str = "checking"
    stage_text: str = "等待开始"
    progress: int = 0
    logs: List[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancel_requested: bool = False
    _task: Optional[asyncio.Task] = None

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{stamp}] {message}")
        # 只保留最近 200 条，避免响应体过大
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]
        self.updated_at = time.time()

    def set_stage(self, stage: str, progress: int, text: str = "") -> None:
        self.stage = stage
        self.progress = max(0, min(100, progress))
        self.stage_text = text or dict(STAGES).get(stage, stage)
        self.updated_at = time.time()

    def to_dict(self, include_result: bool = False) -> dict:
        data = {
            "taskId": self.id,
            "status": self.status,
            "stage": self.stage,
            "stageText": self.stage_text,
            "progress": self.progress,
            "logs": self.logs[-60:],
            "detail": self.detail,
            "error": self.error,
            "criteria": self.criteria,
            "elapsed": round(time.time() - self.created_at, 1),
        }
        if include_result:
            data["result"] = self.result
        return data


def create_task(criteria: dict) -> CollectTask:
    task = CollectTask(id=uuid.uuid4().hex[:16], criteria=criteria)
    _TASKS[task.id] = task
    # 清理最旧的任务
    if len(_TASKS) > MAX_TASKS:
        for old_id in sorted(_TASKS, key=lambda k: _TASKS[k].created_at)[: len(_TASKS) - MAX_TASKS]:
            if _TASKS[old_id].status in (STATUS_DONE, STATUS_FAILED):
                _TASKS.pop(old_id, None)
    return task


def get_task(task_id: str) -> Optional[CollectTask]:
    return _TASKS.get(task_id)


def latest_task() -> Optional[CollectTask]:
    if not _TASKS:
        return None
    return _TASKS[max(_TASKS, key=lambda k: _TASKS[k].created_at)]


# ---------------- 采集执行 ----------------

# 每个站用哪些关键词去搜。转租/直租的信息密度明显高于泛搜"租房"（实测：
# 小红书"租房"单次 2-5 条 vs "转租" 12-16 条），所以优先用这些词。
KEYWORD_SUFFIXES = ["转租", "直租"]


async def _stage_collect(task: CollectTask, criteria: dict) -> dict:
    """到各平台按站点关键词实时搜索并入库"""
    from backend.crawlers.browser_fetch import (
        BrowserSession,
        search_goofish,
        search_xiaohongshu,
        xhs_is_listing,
    )
    from backend.crawlers.base import RawHouse, extract_price
    from backend.crawlers.manager import CrawlerManager
    from backend.database import SessionLocal
    from backend.services.condition import infer_rent_type

    sources: List[str] = criteria.get("sources") or ["xianyu", "xiaohongshu", "douban"]
    city = criteria.get("city") or "深圳"
    stations: List[str] = criteria.get("stations") or []
    max_stations = int(criteria.get("maxStations") or 6)
    stations = stations[:max_stations]

    db = SessionLocal()
    manager = CrawlerManager(db)
    counters = {"cards": 0, "new": 0, "updated": 0, "bySource": {}}
    try:
        # 浏览器类来源（需要页面签名，必须走真实浏览器）
        browser_sources = [s for s in sources if s in ("xianyu", "xiaohongshu")]
        if browser_sources:
            total_steps = max(1, len(browser_sources) * len(stations) * len(KEYWORD_SUFFIXES))
            step = 0
            try:
                async with BrowserSession(cdp_port=criteria.get("cdpPort") or 9222) as session:
                    for station in stations:
                        if task.cancel_requested:
                            task.log("收到取消请求，停止采集")
                            break
                        for suffix in KEYWORD_SUFFIXES:
                            query = f"{station} {suffix}"
                            for source in browser_sources:
                                step += 1
                                progress = 5 + int(55 * step / total_steps)
                                task.set_stage("collecting", progress,
                                               f"搜索 {query}（{source}）")
                                try:
                                    if source == "xianyu":
                                        cards = await search_goofish(session, query, wait_ms=6000)
                                        raw = _cards_to_raw(cards, station, city)
                                    else:
                                        cards = await search_xiaohongshu(session, query, wait_ms=7000)
                                        raw = _xhs_to_raw(cards, station, city, xhs_is_listing)
                                except Exception as e:
                                    task.log(f"⚠️ {query}（{source}）失败：{type(e).__name__}")
                                    continue

                                counters["cards"] += len(cards)
                                if raw:
                                    inserted, updated = manager._process_houses(raw, source)
                                    counters["new"] += inserted
                                    counters["updated"] += updated
                                    counters["bySource"][source] = (
                                        counters["bySource"].get(source, 0) + inserted)
                                    task.log(f"✅ {query}（{source}）"
                                             f"抓到 {len(cards)} → 新增 {inserted}")
                                else:
                                    task.log(f"⚪ {query}（{source}）无房源类结果")
                                await asyncio.sleep(2.5)
            except Exception as e:
                task.log(f"⚠️ 浏览器采集不可用：{type(e).__name__}: {str(e)[:60]}")
                if "playwright" in str(e).lower() or isinstance(e, ImportError):
                    task.log("   原因：未安装 playwright（闲鱼/小红书采集必需）")
                    task.log("   安装：pip install playwright && python -m playwright install chromium")
                else:
                    task.log("   提示：需要先运行 python browser_daemon.py 并完成登录")

        # 豆瓣走直连接口（登录后可用）
        if "douban" in sources:
            task.set_stage("collecting", 62, "搜索 豆瓣")
            try:
                from backend.config import get_settings
                from backend.crawlers.douban import DoubanCrawler
                crawler = DoubanCrawler(cookie=get_settings().douban_cookie or "")
                try:
                    houses = await crawler.search(city=city, keyword="", page=1)
                    if houses:
                        inserted, updated = manager._process_houses(houses, "douban")
                        counters["new"] += inserted
                        counters["updated"] += updated
                        counters["bySource"]["douban"] = inserted
                        task.log(f"✅ 豆瓣：新增 {inserted} 条")
                    else:
                        task.log(f"⚪ 豆瓣：{crawler.last_message or '无结果'}")
                finally:
                    await crawler.close()
            except Exception as e:
                task.log(f"⚠️ 豆瓣采集失败：{type(e).__name__}: {str(e)[:60]}")
    finally:
        db.close()

    task.detail["collect"] = counters
    return counters


def _cards_to_raw(cards, station: str, city: str):
    """闲鱼卡片 → RawHouse"""
    from backend.crawlers.base import RawHouse
    from backend.services.condition import infer_rent_type

    out = []
    for card in cards:
        price = None
        if card.price_text:
            try:
                v = int(float(card.price_text.replace(",", "")))
                price = v if 100 <= v <= 100000 else None
            except ValueError:
                price = None
        out.append(RawHouse(
            source="xianyu", source_id=card.item_id, source_url=card.url,
            title=card.title, description=card.raw_text, city=city, price=price,
            rent_type=infer_rent_type(card.title, card.raw_text),
            publish_time=None,
            images=[card.image] if card.image else [],
            tags=[city, station, "闲鱼"],
            raw_data={"query": card.query, "station_hint": station},
        ))
    return out


def _xhs_to_raw(cards, station: str, city: str, is_listing) -> list:
    """小红书笔记卡片 → RawHouse（只保留"出租房源"类）"""
    import re

    from backend.crawlers.base import RawHouse, extract_price
    from backend.services.condition import infer_rent_type

    out = []
    for card in cards:
        title = card.get("title") or ""
        if not is_listing(title, card.get("text") or ""):
            continue
        m = re.search(r"/explore/([0-9a-f]+)", card.get("href") or "")
        if not m:
            continue
        text = card.get("text") or title
        out.append(RawHouse(
            source="xiaohongshu", source_id=m.group(1),
            source_url=f"https://www.xiaohongshu.com/explore/{m.group(1)}",
            title=title[:200], description=text[:500], city=city,
            price=extract_price(title) or extract_price(text),
            rent_type=infer_rent_type(title, text),
            publish_time=None,
            images=[card["img"]] if card.get("img") else [],
            publisher=(card.get("author") or "").split("\n")[0] or None,
            tags=[city, station, "小红书"],
            raw_data={"query": card.get("query"), "station_hint": station},
        ))
    return out


async def _stage_locate(task: CollectTask, criteria: dict) -> dict:
    """给缺坐标的房源做定位（同步阻塞，放线程池）"""
    def work():
        from backend.database import SessionLocal
        from backend.services import geolocate as gl
        from backend.services.amap import AmapClient

        db = SessionLocal()
        amap = AmapClient()
        try:
            result = gl.locate_batch(
                db, amap, city=criteria.get("city") or "深圳",
                limit=int(criteria.get("locateLimit") or 200),
                max_amap_calls=400)
            return result
        finally:
            amap.close()
            db.close()

    task.set_stage("locating", 70, "推断房源位置")
    result = await asyncio.to_thread(work)
    task.detail["locate"] = {"total": result.get("total"),
                             "located": result.get("located"),
                             "failed": result.get("failed")}
    task.log(f"定位：处理 {result.get('total')} 条，成功 {result.get('located')} 条")
    return result


async def _stage_match(task: CollectTask, criteria: dict) -> dict:
    """套用筛选条件（含真实步行距离计算）"""
    def work():
        from backend.database import SessionLocal
        from backend.services import match as match_service
        from backend.services.amap import AmapClient

        profile = match_service.Profile(
            name="_task",
            city=criteria.get("city") or "深圳",
            stations=criteria.get("stations") or [],
            max_straight_m=int(criteria.get("maxStraightM") or 1000),
            max_walk_minutes=int(criteria.get("maxWalkMinutes") or 20),
            price_min=criteria.get("priceMin"),
            price_max=criteria.get("priceMax"),
            layouts=criteria.get("layouts") or [],
            rent_types=criteria.get("rentTypes") or [],
            exclude_shared=bool(criteria.get("excludeShared", True)),
            require_elevator=bool(criteria.get("requireElevator", False)),
            require_precise_location=bool(criteria.get("requirePreciseLocation", True)),
            avoid_old_small=bool(criteria.get("avoidOldSmall", True)),
            sources=criteria.get("sources") or [],
            listing_kinds=criteria.get("listingKinds") or [],
            poster_types=criteria.get("posterTypes") or [],
            exclude_agency=bool(criteria.get("excludeAgency", False)),
            sort_by=criteria.get("sortBy") or "walk",
        )
        db = SessionLocal()
        amap = AmapClient()
        try:
            return match_service.match(
                db, profile, amap=amap,
                compute_walk=bool(criteria.get("computeWalk", True)),
                max_walk_calls=int(criteria.get("maxWalkCalls") or 150))
        finally:
            amap.close()
            db.close()

    task.set_stage("distance", 82, "计算真实步行距离并筛选")
    result = await asyncio.to_thread(work)
    matched = result.get("matched") or []
    pending = result.get("pendingLocation") or []
    return {
        "success": result.get("success", True),
        "message": result.get("message"),
        "criteria": result.get("profile"),
        "stats": result.get("stats"),
        "total": len(matched),
        "data": [m.__dict__ for m in matched],
        "pendingLocation": [m.__dict__ for m in pending],
    }


async def run_task(task: CollectTask) -> None:
    """任务主流程"""
    criteria = task.criteria
    try:
        task.status = STATUS_RUNNING
        task.set_stage("checking", 3, "检查平台登录状态")
        task.log(f"开始：城市 {criteria.get('city')}，"
                 f"{len(criteria.get('stations') or [])} 个站，"
                 f"来源 {'、'.join(criteria.get('sources') or []) or '全部'}")

        # ① 登录态检查（只做提示，不阻断——豆瓣等未登录也能拿到部分数据）
        try:
            from backend.services import integrations
            status = integrations.integration_status()
            usable = [s["name"] for s in status["sources"]
                      if s["enabled"] and (s["cookieConfigured"] or s["access"] == "http")]
            missing = [s["name"] for s in status["sources"]
                       if s["enabled"] and not s["cookieConfigured"]]
            task.detail["sources"] = {
                "usable": usable, "missingLogin": missing,
                "amapAvailable": status["amap"]["available"],
            }
            if missing:
                task.log(f"⚠️ 未检测到登录态：{'、'.join(missing)}（可能拿不到数据）")
            if not status["amap"]["available"]:
                task.log("⚠️ 未配置高德 Web 服务 Key，无法计算真实步行距离")
        except Exception as e:
            task.log(f"⚠️ 登录态检查失败：{type(e).__name__}")

        if task.cancel_requested:
            raise asyncio.CancelledError()

        # ② 采集
        await _stage_collect(task, criteria)

        if task.cancel_requested:
            raise asyncio.CancelledError()

        # ③ 定位
        await _stage_locate(task, criteria)

        # ④ 筛选（含步行距离）
        result = await _stage_match(task, criteria)

        task.result = result
        task.status = STATUS_DONE
        task.set_stage("done", 100, "完成")
        task.log(f"完成：精确符合 {result.get('total', 0)} 套，"
                 f"位置待确认 {len(result.get('pendingLocation') or [])} 套")
    except asyncio.CancelledError:
        task.status = STATUS_FAILED
        task.error = "任务已取消"
        task.set_stage("done", 100, "已取消")
    except Exception as e:
        import traceback
        task.status = STATUS_FAILED
        task.error = f"{type(e).__name__}: {e}"
        task.set_stage("done", 100, "失败")
        task.log(f"❌ 任务失败：{type(e).__name__}: {str(e)[:120]}")
        task.log(traceback.format_exc()[-400:])


def start_task(task: CollectTask) -> None:
    """把任务挂到当前事件循环上执行（不阻塞请求）"""
    task._task = asyncio.create_task(run_task(task))
