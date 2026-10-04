"""房源 → 地铁站的步行距离

关键约定：
- 对外展示与筛选的**只有真实步行路径距离**（高德步行规划返回的 distance/duration），
  直线距离仅作为"是否需要计算"的预筛条件，单独存字段、单独展示。
- 结果落库缓存（station_distances 表，house_id + station_id 唯一），
  重复筛选不必重复调用高德，可断点续算。
- 高德返回"无法规划步行路径"时记为 no_route，**不拿直线距离顶替**。
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import House, MetroStation, StationDistance
from backend.services.amap import AmapClient, haversine_meters

# 超过这个直线距离就不做步行规划（省配额，且现实中已不属于"地铁房"）
PREFILTER_STRAIGHT_M = 3000


def get_cached(db: Session, house_id: str, station_id: str) -> Optional[StationDistance]:
    return db.query(StationDistance).filter(
        StationDistance.house_id == house_id,
        StationDistance.station_id == station_id,
    ).first()


def compute_for_station(
    db: Session,
    station: MetroStation,
    amap: AmapClient,
    city: str = "深圳",
    limit: int = 500,
    only_missing: bool = True,
    max_amap_calls: int = 400,
    prefilter_m: int = PREFILTER_STRAIGHT_M,
) -> Dict:
    """计算某站点到各房源的步行距离（可重复执行、增量续算）"""
    if station.lng is None or station.lat is None:
        return {
            "success": False,
            "message": f"站点「{station.name}」缺少坐标，无法计算。"
                       f"请先同步高德地铁数据或手动补坐标。",
            "computed": 0, "noRoute": 0, "skipped": 0, "amapCalls": 0,
        }

    if not amap.available:
        return {"success": False,
                "message": "未配置 AMAP_WEB_KEY，无法计算步行距离",
                "computed": 0, "noRoute": 0, "skipped": 0, "amapCalls": 0}

    # 候选：有坐标的房源
    query = db.query(House).filter(
        House.city == city,
        House.longitude.isnot(None),
        House.latitude.isnot(None),
    )
    houses: List[House] = query.all()

    # 已缓存集合
    cached_ids = set()
    if only_missing:
        cached_ids = {
            row[0] for row in db.query(StationDistance.house_id).filter(
                StationDistance.station_id == station.id,
                StationDistance.status == "ok",
            ).all()
        }

    started_calls = amap.calls
    computed = no_route = skipped = errors = 0
    queued: List[tuple] = []

    for house in houses:
        if house.id in cached_ids:
            skipped += 1
            continue
        straight = haversine_meters(station.lng, station.lat,
                                    house.longitude, house.latitude)
        if straight > prefilter_m:
            skipped += 1
            continue
        queued.append((straight, house))

    # 近的优先算，这样即使配额用尽，用户最关心的"近地铁"房源也已经算好
    queued.sort(key=lambda x: x[0])
    queued = queued[:limit]

    for straight, house in queued:
        if amap.calls - started_calls >= max_amap_calls:
            break

        record = get_cached(db, house.id, station.id)
        if record is None:
            record = StationDistance(house_id=house.id, station_id=station.id)
            db.add(record)

        record.straight_meters = straight
        record.provider = "amap"
        record.computed_at = datetime.now()

        try:
            result = amap.walking((house.longitude, house.latitude),
                                  (station.lng, station.lat))
        except Exception as e:
            record.status = "error"
            record.message = f"{type(e).__name__}: {e}"[:255]
            record.walk_meters = None
            record.walk_minutes = None
            errors += 1
            db.commit()
            continue

        if result is None:
            record.status = "no_route"
            record.message = "高德无法规划步行路径（起终点过近或不可步行到达）"
            record.walk_meters = None
            record.walk_minutes = None
            no_route += 1
        else:
            record.status = "ok"
            record.message = None
            record.walk_meters = result.distance_m
            record.walk_minutes = result.minutes
            computed += 1

        db.commit()

    db.commit()

    return {
        "success": True,
        "station": station.name,
        "computed": computed,
        "noRoute": no_route,
        "errors": errors,
        "skipped": skipped,
        "queued": len(queued),
        "amapCalls": amap.calls - started_calls,
        "cacheHits": amap.cache_hits,
        "message": f"已计算 {computed} 条步行距离"
                   + (f"，{no_route} 条无法步行到达" if no_route else "")
                   + (f"，{skipped} 条已缓存或超出 {prefilter_m}m 预筛范围" if skipped else ""),
    }


def station_coverage(db: Session, station_id: str) -> Dict:
    """某站点已计算覆盖情况"""
    total = db.query(StationDistance).filter(
        StationDistance.station_id == station_id).count()
    ok = db.query(StationDistance).filter(
        StationDistance.station_id == station_id,
        StationDistance.status == "ok").count()
    no_route = db.query(StationDistance).filter(
        StationDistance.station_id == station_id,
        StationDistance.status == "no_route").count()
    return {"cached": total, "ok": ok, "noRoute": no_route}
