"""按"通勤选址需求"匹配房源

用户的实际决策方式不是"先看房源再想通勤"，而是：
**先定几个地铁站 + 预算 + 房型 + 通勤容忍度，再问"有哪些房能满足"**。
本模块就是这条路径的实现。

匹配链路（每一步都尽量省 API 调用）：
    价格 / 房型（数据库索引）
      → 直线距离预筛（纯计算，零成本）
      → 真实步行距离（高德，只对预筛幸存者调用，结果缓存）
      → 条件筛选（电梯 / 新旧 / 老破小）
      → 排序并给出"为什么它符合"的逐条理由

坐标缺失的房源会先尝试定位；定位失败则如实排除，
并单独统计"因缺坐标未能判断"的数量，不会静默丢掉。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import House, MetroStation, StationDistance
from backend.services.amap import AmapClient, haversine_meters
from backend.services.condition import analyze_condition, condition_summary
from backend.services.layout import LAYOUT_LABELS

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "profiles")


@dataclass
class Profile:
    """通勤选址需求档案"""
    name: str
    city: str = "深圳"
    stations: List[str] = field(default_factory=list)
    max_straight_m: int = 1000          # 直线距离上限（米）
    max_walk_minutes: int = 20          # 步行时间上限（分钟）
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    layouts: List[str] = field(default_factory=list)   # studio / 1b1l / 2b1l
    require_elevator: bool = False      # 是否要求"明确写了有电梯"
    min_newness_score: Optional[int] = None
    avoid_old_small: bool = True        # 排除老破小类特征
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Profile":
        known = {f for f in Profile.__dataclass_fields__}
        return Profile(**{k: v for k, v in data.items() if k in known})

    def path(self) -> str:
        safe = "".join(c for c in self.name if c.isalnum() or c in "-_") or "profile"
        return os.path.join(PROFILE_DIR, f"{safe}.json")

    def save(self) -> str:
        os.makedirs(PROFILE_DIR, exist_ok=True)
        path = self.path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    @staticmethod
    def load(name: str) -> "Profile":
        safe = "".join(c for c in name if c.isalnum() or c in "-_") or "profile"
        path = os.path.join(PROFILE_DIR, f"{safe}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"需求档案不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return Profile.from_dict(json.load(f))


@dataclass
class MatchedHouse:
    house_id: str
    title: str
    price: Optional[int]
    layout_label: str
    source: str
    source_url: str
    district: Optional[str]
    community: Optional[str]
    nearest_station: str
    nearest_station_lines: List[str]
    straight_m: int
    walk_m: Optional[int]
    walk_minutes: Optional[int]
    walk_status: str
    elevator: Optional[bool]
    elevator_evidence: Optional[str]
    elevator_hint: Optional[str]
    newness_score: int
    newness_signals: List[str]
    old_small: bool
    geo_source: Optional[str]
    geo_precision: Optional[str]
    reasons: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)


def _station_lines(db: Session, station: MetroStation) -> List[str]:
    from backend.models import MetroLine, MetroLineStation
    rows = db.query(MetroLine.name).join(
        MetroLineStation, MetroLineStation.line_id == MetroLine.id
    ).filter(MetroLineStation.station_id == station.id).all()
    return sorted({r[0] for r in rows})


def match(db: Session, profile: Profile, amap: Optional[AmapClient] = None,
          compute_walk: bool = True, max_walk_calls: int = 120,
          locate_missing: bool = False) -> Dict:
    """按需求档案匹配房源"""
    # ---------- 1) 基础筛选：城市 / 价格 / 房型 ----------
    query = db.query(House).filter(House.city == profile.city)
    if profile.price_min is not None:
        query = query.filter(House.price >= profile.price_min)
    if profile.price_max is not None:
        query = query.filter(House.price <= profile.price_max)
    if profile.layouts:
        query = query.filter(House.layout_key.in_(profile.layouts))
    candidates = query.all()

    # ---------- 2) 站点坐标 ----------
    stations: List[MetroStation] = []
    missing_stations: List[str] = []
    for name in profile.stations:
        station = db.query(MetroStation).filter(
            MetroStation.city == profile.city, MetroStation.name == name).first()
        if station is None or station.lng is None:
            missing_stations.append(name)
        else:
            stations.append(station)

    if not stations:
        return {"success": False,
                "message": f"没有可用站点（缺坐标：{missing_stations}）",
                "matched": [], "stats": {}}

    # ---------- 3) 直线距离预筛（零成本）----------
    no_coord: List[House] = []
    within_straight: List[tuple] = []      # (house, station, straight_m)
    for house in candidates:
        if house.longitude is None or house.latitude is None:
            no_coord.append(house)
            continue
        best = None
        for station in stations:
            d = haversine_meters(house.longitude, house.latitude,
                                 station.lng, station.lat)
            if best is None or d < best[1]:
                best = (station, d)
        if best and best[1] <= profile.max_straight_m:
            within_straight.append((house, best[0], best[1]))

    # ---------- 4) 可选：先给缺坐标的房源定位 ----------
    located_now = 0
    if locate_missing and amap is not None and amap.available and no_coord:
        from backend.services.geolocate import locate_house
        for house in no_coord[:30]:
            outcome = locate_house(db, house, amap)
            if outcome.success and house.longitude is not None:
                located_now += 1
                best = None
                for station in stations:
                    d = haversine_meters(house.longitude, house.latitude,
                                         station.lng, station.lat)
                    if best is None or d < best[1]:
                        best = (station, d)
                if best and best[1] <= profile.max_straight_m:
                    within_straight.append((house, best[0], best[1]))

    # ---------- 5) 真实步行距离 ----------
    walk_calls = 0
    walk_skipped_no_key = False
    results: List[MatchedHouse] = []
    dropped_by_walk = 0
    walk_unknown = 0

    station_lines_cache: Dict[str, List[str]] = {}

    for house, station, straight in within_straight:
        record = db.query(StationDistance).filter(
            StationDistance.house_id == house.id,
            StationDistance.station_id == station.id).first()

        walk_m = walk_minutes = None
        status = "未计算"

        if record is not None and record.status == "ok":
            walk_m, walk_minutes, status = record.walk_meters, record.walk_minutes, "ok"
        elif compute_walk and amap is not None and amap.available and walk_calls < max_walk_calls:
            try:
                walking = amap.walking((house.longitude, house.latitude),
                                       (station.lng, station.lat))
            except Exception:
                walking = None
            walk_calls += 1
            if record is None:
                record = StationDistance(house_id=house.id, station_id=station.id)
                db.add(record)
            record.straight_meters = straight
            record.provider = "amap"
            record.computed_at = datetime.now()
            if walking is None:
                record.status = "no_route"
                record.message = "高德无法规划步行路径"
                status = "no_route"
            else:
                record.status = "ok"
                record.walk_meters = walking.distance_m
                record.walk_minutes = walking.minutes
                record.message = None
                walk_m, walk_minutes, status = walking.distance_m, walking.minutes, "ok"
            db.commit()
        elif not (amap and amap.available):
            walk_skipped_no_key = True

        # 步行时间超限 → 淘汰
        if walk_minutes is not None and walk_minutes > profile.max_walk_minutes:
            dropped_by_walk += 1
            continue
        if walk_minutes is None:
            walk_unknown += 1

        # ---------- 6) 条件识别 ----------
        condition = analyze_condition(house.title, house.description,
                                      tags=house.tags,
                                      floor_text=(house.raw_data or ""))
        if profile.require_elevator and condition.elevator is False:
            continue
        if profile.avoid_old_small and condition.old_small:
            continue
        if (profile.min_newness_score is not None
                and condition.newness_score < profile.min_newness_score):
            continue

        if station.id not in station_lines_cache:
            station_lines_cache[station.id] = _station_lines(db, station)

        # ---------- 7) 逐条给出"为什么符合" ----------
        reasons = [
            f"{station.name}站 直线 {straight}m"
            + (f"／步行 {walk_minutes} 分钟（{walk_m}m）" if walk_minutes else "（步行未计算）"),
            f"价格 {house.price} 元在预算内"
            if house.price else "价格未知",
            f"房型 {LAYOUT_LABELS.get(house.layout_key or '', '未知')}",
        ]
        if condition.elevator is True:
            reasons.append(f"明确写了电梯（{condition.elevator_evidence}）")
        if condition.newness_score >= 70:
            reasons.append("新旧信号偏新：" + "/".join(condition.newness_signals[:3]))

        caveats = []
        if condition.elevator is None:
            caveats.append(condition.elevator_hint or "电梯未标注，需现场/电话确认")
        if walk_minutes is None:
            caveats.append("步行距离未计算")
        if house.geo_precision in ("station",):
            caveats.append("坐标按地铁站近似，实际位置可能偏差")

        results.append(MatchedHouse(
            house_id=house.id, title=house.title, price=house.price,
            layout_label=LAYOUT_LABELS.get(house.layout_key or "", "未知"),
            source=house.source, source_url=house.source_url,
            district=house.district, community=house.community,
            nearest_station=station.name,
            nearest_station_lines=station_lines_cache[station.id],
            straight_m=straight, walk_m=walk_m, walk_minutes=walk_minutes,
            walk_status=status,
            elevator=condition.elevator,
            elevator_evidence=condition.elevator_evidence,
            elevator_hint=condition.elevator_hint,
            newness_score=condition.newness_score,
            newness_signals=condition.newness_signals,
            old_small=condition.old_small,
            geo_source=house.geo_source, geo_precision=house.geo_precision,
            reasons=reasons, caveats=caveats,
        ))

    # ---------- 8) 排序：先按步行时间，再按新旧 ----------
    results.sort(key=lambda m: (
        m.walk_minutes if m.walk_minutes is not None else 999,
        m.straight_m,
        -m.newness_score,
    ))

    return {
        "success": True,
        "profile": profile.to_dict(),
        "matched": results,
        "stats": {
            "priceLayoutCandidates": len(candidates),
            "stationsUsed": len(stations),
            "stationsMissing": missing_stations,
            "withoutCoord": len(no_coord),
            "locatedNow": located_now,
            "withinStraight": len(within_straight),
            "droppedByWalkTime": dropped_by_walk,
            "walkUnknown": walk_unknown,
            "matched": len(results),
            "walkApiCalls": walk_calls,
            "amapKeyMissing": walk_skipped_no_key,
        },
    }


def render_report(result: Dict, limit: int = 50) -> str:
    """把匹配结果渲染成可读报告"""
    profile = result.get("profile") or {}
    stats = result.get("stats") or {}
    matched: List[MatchedHouse] = result.get("matched") or []

    lines = []
    lines.append("=" * 78)
    lines.append(f"需求档案：{profile.get('name')}（{profile.get('city')}）")
    lines.append(f"站点：{'、'.join(profile.get('stations') or [])}")
    lines.append(f"预算：{profile.get('price_min')}-{profile.get('price_max')} 元/月    "
                 f"房型：{'/'.join(LAYOUT_LABELS.get(k, k) for k in (profile.get('layouts') or []))}")
    lines.append(f"距离：直线 ≤ {profile.get('max_straight_m')}m 且 步行 ≤ "
                 f"{profile.get('max_walk_minutes')} 分钟")
    lines.append("=" * 78)

    lines.append(f"\n候选 {stats.get('priceLayoutCandidates')} 条 → "
                 f"直线达标 {stats.get('withinStraight')} 条 → "
                 f"最终符合 {stats.get('matched')} 条")
    detail = []
    if stats.get("withoutCoord"):
        detail.append(f"{stats['withoutCoord']} 条缺坐标")
    if stats.get("locatedNow"):
        detail.append(f"本次新定位 {stats['locatedNow']} 条")
    if stats.get("droppedByWalkTime"):
        detail.append(f"{stats['droppedByWalkTime']} 条步行超时被淘汰")
    if stats.get("walkUnknown"):
        detail.append(f"{stats['walkUnknown']} 条步行未计算")
    if stats.get("stationsMissing"):
        detail.append(f"缺站点坐标：{stats['stationsMissing']}")
    if detail:
        lines.append("   （" + "；".join(detail) + "）")
    if stats.get("amapKeyMissing"):
        lines.append("   ⚠️ 未配置 AMAP_WEB_KEY：无法计算真实步行距离")

    if not matched:
        lines.append("\n没有符合条件的房源。")
        lines.append("可能原因：该预算/房型在地铁 1km 内的供给很少，或数据还没采到。")
        return "\n".join(lines)

    lines.append("")
    for i, m in enumerate(matched[:limit], 1):
        walk = f"步行{m.walk_minutes}分钟/{m.walk_m}m" if m.walk_minutes else "步行未计算"
        elev = ("✅有电梯" if m.elevator is True
                else ("❌无电梯" if m.elevator is False else "❓电梯未标注"))
        lines.append(f"{i:2}. [{m.price}元] {m.title[:42]}")
        lines.append(f"    {m.nearest_station}站({'/'.join(m.nearest_station_lines)}) "
                     f"直线{m.straight_m}m | {walk} | {m.layout_label} | {elev} | 新旧{m.newness_score}")
        if m.community or m.district:
            lines.append(f"    位置：{m.district or ''} {m.community or ''}".rstrip())
        lines.append(f"    来源：{m.source}  {m.source_url}")
        if m.caveats:
            lines.append(f"    ⚠️ {'；'.join(m.caveats)}")
        lines.append("")
    return "\n".join(lines)
