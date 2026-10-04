"""房源位置推断

目标：为没有坐标的房源（豆瓣全都没有，贝壳详情页被验证码挡住）找到**可信且可溯源**的位置。

流程：
    文本 → 候选地点（小区/地址/地铁站/商圈）
         → 高德 POI 搜索 / 地理编码
         → 反向地理编码校验（区县是否一致）
         → 写入坐标 + 来源 + 精度 + 置信度

三条硬规则：
1. **不伪造坐标**：只有 building/community/street/station 级别的结果才写入；
   只匹配到"区/市"级别时坐标留空（否则地图上会出现一堆假点）。
2. **必须溯源**：每条坐标都记录 `geo_source`（platform/amap_poi/amap_geocode/
   llm_text/llm_image/manual）与 `geo_precision`，界面要能区分。
3. **不覆盖更好的数据**：已有平台原始坐标时，推断结果不覆盖它。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import House
from backend.services.amap import AmapClient, GeoResult, PoiResult

# 精度等级（越大越精确），用于决定是否覆盖已有值
PRECISION_RANK = {
    "unknown": 0,
    "district": 1,
    "station": 2,
    "street": 3,
    "community": 4,
    "building": 5,
}

# 只有这些精度才允许写入坐标
ACCEPTED_PRECISION = {"station", "street", "community", "building"}

# 小区/楼盘常见后缀
RE_COMMUNITY = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9·]{2,18}?"
    r"(?:小区|花园|新村|公寓|大厦|广场|公馆|名苑|雅苑|家园|华府|国际|中心|湾|苑|城|府|里|村|园))"
)
# 地铁站提及： "近1号线深大站" / "地铁3号线布吉站" / "深大站"
RE_STATION = re.compile(r"(?:地铁)?\s*(?:\d{1,2}号线|[一二三四五六七八九十]{1,2}号线)?\s*"
                        r"([\u4e00-\u9fa5]{2,8}?)站")
# 距离表述："距地铁站500米" —— 用于判断"近站"表述的可信度
RE_NEAR_STATION_DIST = re.compile(r"(\d{2,5})\s*(?:米|m|M)\s*(?:到|至|左右)?")

CN_DIGITS = {"一": "1", "二": "2", "两": "2", "三": "3", "四": "4", "五": "5",
             "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}


@dataclass
class LocationCandidate:
    """一个待验证的地点候选"""
    query: str
    kind: str            # community / address / station / area
    confidence: int      # 初始置信度
    evidence: str = ""   # 命中依据（便于人工核对）
    expect_precision: str = "community"


@dataclass
class LocateOutcome:
    success: bool
    message: str
    lng: Optional[float] = None
    lat: Optional[float] = None
    source: Optional[str] = None
    precision: Optional[str] = None
    confidence: Optional[int] = None
    query: Optional[str] = None
    note: Optional[str] = None


# ---------- 候选抽取 ----------

def normalize_line_name(text: str) -> str:
    """把"三号线"统一成"3号线"，便于拼接查询串"""
    for cn, digit in CN_DIGITS.items():
        text = text.replace(f"{cn}号线", f"{digit}号线")
    return text


def extract_candidates(house: House, max_candidates: int = 4) -> List[LocationCandidate]:
    """从房源字段与文本中抽取地点候选，按可信度排序"""
    title = house.title or ""
    description = house.description or ""
    tags = house.tags or ""
    blob = normalize_line_name(" ".join([title, description, tags]))

    candidates: List[LocationCandidate] = []

    # 1) 平台结构化字段最可信
    if house.community:
        candidates.append(LocationCandidate(
            query=house.community, kind="community", confidence=88,
            evidence="平台字段 community", expect_precision="community"))
    if house.address:
        candidates.append(LocationCandidate(
            query=house.address, kind="address", confidence=82,
            evidence="平台字段 address", expect_precision="building"))
    if house.area:
        prefix = f"{house.district or ''}{house.area}"
        candidates.append(LocationCandidate(
            query=prefix, kind="area", confidence=62,
            evidence="平台字段 district+area(商圈)", expect_precision="community"))

    # 2) 正文里的小区名
    for match in RE_COMMUNITY.finditer(blob):
        name = match.group(1).strip("·- ")
        # 过滤明显不是小区的词
        if len(name) < 3 or name in {"青年公寓", "品牌公寓", "服务公寓"}:
            continue
        candidates.append(LocationCandidate(
            query=name, kind="community", confidence=70,
            evidence=f"正文命中: {name}", expect_precision="community"))
        if len(candidates) >= max_candidates + 3:
            break

    # 3) 地铁站（只能定位到"站点附近"，置信度明显更低）
    for match in RE_STATION.finditer(blob):
        name = match.group(1).strip()
        if len(name) < 2 or name in {"地", "地铁", "本", "该"}:
            continue
        candidates.append(LocationCandidate(
            query=f"{name}站", kind="station", confidence=45,
            evidence=f"正文提及地铁站: {name}站", expect_precision="station"))

    # 去重（同 query 保留置信度最高的）
    dedup: Dict[str, LocationCandidate] = {}
    for item in candidates:
        key = item.query.strip()
        if not key:
            continue
        if key not in dedup or item.confidence > dedup[key].confidence:
            dedup[key] = item

    ordered = sorted(dedup.values(), key=lambda x: -x.confidence)
    return ordered[:max_candidates]


# ---------- 单个候选求解 ----------

def _name_similarity(a: str, b: str) -> float:
    """粗糙的名称相似度：完全包含关系算高，否则按字符重合"""
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85
    common = len(set(a) & set(b))
    return common / max(len(set(a)), len(set(b)))


def resolve_candidate(amap: AmapClient, candidate: LocationCandidate,
                      city: str) -> Optional[LocateOutcome]:
    """把一个候选地点解析成坐标"""
    if candidate.kind == "station":
        pois = amap.place_text(keywords=candidate.query, city=city, types="150500")
        if not pois:
            pois = amap.place_text(keywords=candidate.query, city=city)
        pois = [p for p in pois if p.name.endswith("站")] or pois
        if not pois:
            return None
        poi = pois[0]
        return LocateOutcome(
            success=True, message="按地铁站定位",
            lng=poi.lng, lat=poi.lat, source="amap_poi", precision="station",
            confidence=min(candidate.confidence, 50),
            query=candidate.query,
            note=f"{candidate.evidence}；坐标为站点位置，房源在其附近",
        )

    # 小区/地址：先 POI 关键字搜索（最准），再退回地理编码
    pois: List[PoiResult] = amap.place_text(keywords=candidate.query, city=city)
    best = None
    best_score = 0.0
    for poi in pois[:8]:
        score = _name_similarity(candidate.query, poi.name)
        # 高德 POI 类型里住宅小区/商务住宅更可能是我们要找的
        if "住宅" in (poi.poi_type or "") or "小区" in (poi.poi_type or ""):
            score += 0.15
        if score > best_score:
            best, best_score = poi, score

    if best is not None and best_score >= 0.5:
        precision = "building" if best_score >= 0.85 else "community"
        confidence = int(min(candidate.confidence, 60 + best_score * 35))
        return LocateOutcome(
            success=True, message="按小区/POI 定位",
            lng=best.lng, lat=best.lat, source="amap_poi", precision=precision,
            confidence=confidence, query=candidate.query,
            note=f"{candidate.evidence} → 高德 POI「{best.name}」相似度 {best_score:.2f}",
        )

    geo: Optional[GeoResult] = amap.geocode(candidate.query, city=city)
    if geo is None:
        return None

    precision = geo.precision
    if precision not in ACCEPTED_PRECISION:
        # 只到区/市级：宁可不写坐标，也不在地图上放一个假点
        return LocateOutcome(
            success=False, message=f"仅定位到 {geo.level or '未知'} 级别，不够精确，坐标留空",
            query=candidate.query,
            note=f"{candidate.evidence} → 高德地理编码级别={geo.level}",
        )

    return LocateOutcome(
        success=True, message="按地理编码定位",
        lng=geo.lng, lat=geo.lat, source="amap_geocode", precision=precision,
        confidence=min(candidate.confidence, 75),
        query=candidate.query,
        note=f"{candidate.evidence} → 地理编码「{geo.formatted_address}」级别={geo.level}",
    )


# ---------- 单条房源定位 ----------

def locate_house(db: Session, house: House, amap: AmapClient,
                 llm_extract: Optional[Callable[[House], Optional[dict]]] = None,
                 overwrite_worse: bool = False) -> LocateOutcome:
    """为一条房源推断坐标并写回数据库"""
    city = house.city or "深圳"

    # 已有平台原始坐标 → 不覆盖（平台数据优先）
    if house.longitude is not None and house.latitude is not None:
        if (house.geo_source or "platform") == "platform" and not overwrite_worse:
            return LocateOutcome(False, "已有平台坐标，跳过",
                                 lng=house.longitude, lat=house.latitude,
                                 source=house.geo_source or "platform")

    if not amap.available:
        return LocateOutcome(False, "未配置 AMAP_WEB_KEY，无法定位")

    candidates = extract_candidates(house)

    # 规则抽取无结果时（或结果很少时）尝试大模型抽取
    if llm_extract is not None and (not candidates or max(c.confidence for c in candidates) < 70):
        try:
            extra = llm_extract(house) or {}
        except Exception as e:
            extra = {}
            house.geo_note = f"大模型抽取失败: {type(e).__name__}"
        for key, kind, conf in (("community", "community", 78),
                                ("address", "address", 76),
                                ("station", "station", 50)):
            value = (extra.get(key) or "").strip() if isinstance(extra, dict) else ""
            if value:
                name = f"{value}站" if kind == "station" and not value.endswith("站") else value
                candidates.append(LocationCandidate(
                    query=name, kind=kind, confidence=conf,
                    evidence=f"大模型抽取({key}): {value}",
                    expect_precision="station" if kind == "station" else "community"))

    if not candidates:
        house.geo_note = "未能从标题/正文中提取到可用地点"
        db.commit()
        return LocateOutcome(False, house.geo_note)

    last_note = ""
    for candidate in candidates:
        try:
            outcome = resolve_candidate(amap, candidate, city)
        except Exception as e:
            last_note = f"高德调用失败: {type(e).__name__}: {e}"
            continue

        if outcome is None:
            last_note = f"「{candidate.query}」未匹配到结果"
            continue

        if not outcome.success:
            last_note = outcome.message
            continue

        # 反向地理编码校验：区县是否一致，不一致就降置信度
        note = outcome.note or ""
        confidence = outcome.confidence or 50
        if house.district:
            try:
                reverse = amap.reverse_geocode(outcome.lng, outcome.lat)
            except Exception:
                reverse = None
            if reverse and reverse.get("district"):
                if house.district in reverse["district"] or reverse["district"] in house.district:
                    confidence = min(100, confidence + 8)
                    note += "；区县校验通过"
                else:
                    confidence = max(10, confidence - 30)
                    note += f"；⚠️ 区县不一致(平台={house.district} 高德={reverse['district']})"

        house.longitude = outcome.lng
        house.latitude = outcome.lat
        house.geo_source = outcome.source
        house.geo_precision = outcome.precision
        house.geo_confidence = confidence
        house.geo_query = outcome.query
        house.geo_note = note[:255]
        house.geo_updated_at = datetime.now()
        db.commit()

        return LocateOutcome(True, f"已定位（{outcome.precision}/{confidence}）",
                             lng=outcome.lng, lat=outcome.lat,
                             source=outcome.source, precision=outcome.precision,
                             confidence=confidence, query=outcome.query, note=note)

    house.geo_note = (last_note or "所有候选均未匹配")[:255]
    db.commit()
    return LocateOutcome(False, house.geo_note)


def locate_batch(db: Session, amap: AmapClient, city: str = "深圳",
                 limit: int = 20, only_missing: bool = True,
                 llm_extract: Optional[Callable] = None,
                 max_amap_calls: int = 200) -> Dict:
    """批量定位。受 max_amap_calls 保护，避免一次跑掉大量配额"""
    query = db.query(House).filter(House.city == city)
    if only_missing:
        query = query.filter(House.longitude.is_(None))
    houses = query.order_by(House.crawl_time.desc()).limit(limit).all()

    started_calls = amap.calls
    located = failed = skipped = 0
    details = []

    for house in houses:
        if amap.calls - started_calls >= max_amap_calls:
            details.append({"id": house.id, "result": "配额保护：本批次已达调用上限"})
            break

        outcome = locate_house(db, house, amap, llm_extract=llm_extract)
        if outcome.success and outcome.lng is not None:
            located += 1
        elif "跳过" in (outcome.message or ""):
            skipped += 1
        else:
            failed += 1
        details.append({"id": house.id, "title": (house.title or "")[:30],
                        "result": outcome.message, "precision": outcome.precision})

    return {
        "total": len(houses),
        "located": located,
        "failed": failed,
        "skipped": skipped,
        "amapCalls": amap.calls - started_calls,
        "cacheHits": amap.cache_hits,
        "details": details[:50],
    }
