"""深圳地铁线路与站点数据

两条数据来源，互为补充：
1. **静态数据** `data/metro/{city}.json`：线路与站点名称（人工核实），
   不依赖网络即可让前端选站；
2. **高德同步** `AmapClient.bus_line()`：真实线路走向与站点坐标，
   有 Key 时用于补齐/校正坐标（名称仍以静态数据为准，避免高德写法差异）。

坐标一律标注来源（static/amap），没有来源就留空，不用城市中心点凑数。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import MetroLine, MetroLineStation, MetroStation
from backend.services.coords import convert_if_wgs84

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "metro")

# 城市名 -> 静态数据文件名（拼音），兼容直接用中文名命名的情况
CITY_FILE_ALIASES = {
    "深圳": "shenzhen", "shenzhen": "shenzhen",
    "上海": "shanghai", "北京": "beijing", "广州": "guangzhou",
}


def static_path(city: str) -> str:
    """定位静态数据文件：优先拼音文件名，其次中文文件名"""
    alias = CITY_FILE_ALIASES.get(city, city)
    for name in (alias, city):
        candidate = os.path.join(DATA_DIR, f"{name}.json")
        if os.path.exists(candidate):
            return candidate
    return os.path.join(DATA_DIR, f"{alias}.json")


def station_match_key(name: str) -> str:
    """站点名归一化，用于跨来源匹配

    高德写作「深圳北」，维基写作「深圳北站」，末尾的「站」需要抹平；
    同时去掉空白与括号内容。
    """
    if not name:
        return ""
    key = re.sub(r"[（(][^）)]*[)）]", "", name)
    key = key.strip().replace(" ", "")
    return re.sub(r"站$", "", key)


@dataclass
class ImportStats:
    lines: int = 0
    stations: int = 0
    links: int = 0
    skipped: int = 0
    message: str = ""


# ---------- 静态数据导入 ----------

def import_static(db: Session, city: str, path: Optional[str] = None) -> ImportStats:
    """把 data/metro/{city}.json 导入数据库（幂等，可重复执行）"""
    path = path or static_path(city)
    stats = ImportStats()

    if not os.path.exists(path):
        stats.message = f"静态数据不存在: {path}"
        return stats

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    line_cache: Dict[str, MetroLine] = {
        line.name: line for line in db.query(MetroLine).filter(MetroLine.city == city)
    }
    station_cache: Dict[str, MetroStation] = {
        s.name: s for s in db.query(MetroStation).filter(MetroStation.city == city)
    }

    for order, item in enumerate(payload.get("lines") or [], start=1):
        name = (item.get("name") or "").strip()
        stations = item.get("stations") or []
        if not name:
            stats.skipped += 1
            continue
        if item.get("status", "operating") != "operating":
            stats.skipped += 1
            continue

        line = line_cache.get(name)
        if line is None:
            line = MetroLine(city=city, name=name)
            db.add(line)
            db.flush()
            line_cache[name] = line
            stats.lines += 1

        line.alias = item.get("alias") or line.alias
        line.color = item.get("color") or line.color
        line.sort_order = order
        line.status = "operating"
        line.source = "static"

        for seq, entry in enumerate(stations, start=1):
            station_name = (entry.get("name") or "").strip() if isinstance(entry, dict) \
                else str(entry).strip()
            if not station_name:
                continue

            station = station_cache.get(station_name)
            if station is None:
                station = MetroStation(city=city, name=station_name)
                db.add(station)
                db.flush()
                station_cache[station_name] = station
                stats.stations += 1

            # 静态坐标只在数据库里没有更新来源时才写入
            if isinstance(entry, dict):
                lng, lat = entry.get("lng"), entry.get("lat")
                if lng is not None and lat is not None and station.lng is None:
                    # 维基/Wikidata 是 WGS-84，必须转成 GCJ-02 才能与高德
                    # 的步行路径规划对齐，否则距离会整体偏移几百米
                    gcj_lng, gcj_lat, _note = convert_if_wgs84(
                        float(lng), float(lat), "wikidata")
                    station.lng, station.lat = gcj_lng, gcj_lat
                    station.coord_source = "wikidata"

            exists = db.query(MetroLineStation).filter(
                MetroLineStation.line_id == line.id,
                MetroLineStation.station_id == station.id,
            ).first()
            if exists:
                exists.seq = seq
            else:
                db.add(MetroLineStation(line_id=line.id, station_id=station.id, seq=seq))
                stats.links += 1

    db.commit()
    stats.message = (f"导入 {stats.lines} 条线路、{stats.stations} 个站点、"
                     f"{stats.links} 条线路站点关联")
    return stats


def ensure_seeded(db: Session, city: str) -> ImportStats:
    """数据库里没有该城市数据时自动导入静态数据"""
    count = db.query(MetroLine).filter(MetroLine.city == city).count()
    if count:
        return ImportStats(message=f"{city} 已有 {count} 条线路，跳过导入")
    return import_static(db, city)


# ---------- 高德坐标与线路同步 ----------

# 高德 POI 类型：地铁站
AMAP_METRO_TYPE = "150500"


def _parse_lines_from_address(address: str) -> List[str]:
    """从高德 POI 的 address 里解析所属线路。

    实测高德地铁站 POI 形如：
        name    = "车公庙(地铁站)"
        address = "11号线/机场线;1号线/罗宝线;7号线/西丽线;9号线/梅林线"
        address = "2号线(8号线)"          # 深圳 2/8 号线贯通运营，两条都要登记

    规则：
    - 按 ; 分隔多个条目
    - 每条取 "/" 之前的主名（"1号线/罗宝线" → "1号线"）
    - 括号里的另一条线也要登记（"2号线(8号线)" → 2号线 + 8号线）
    """
    if not address:
        return []

    lines: List[str] = []

    def add(name: str):
        name = name.strip()
        if name and name not in lines:
            lines.append(name)

    for chunk in re.split(r"[;；]", address):
        chunk = chunk.strip()
        if not chunk:
            continue
        primary = chunk.split("/")[0].strip()
        for extra in re.findall(r"[（(]([^）)]+)[)）]", primary):
            add(extra)
        add(re.sub(r"[（(][^）)]*[)）]", "", primary))
    return lines


def _clean_station_name(name: str) -> str:
    """去掉高德 POI 名称里的后缀，如 "深大(地铁站)" → "深大" """
    if not name:
        return ""
    return re.sub(r"[（(]地铁站[)）]$", "", name.strip()).strip()


def refresh_from_amap_poi(db: Session, city: str, amap,
                          max_pages: int = 20, page_size: int = 25,
                          overwrite: bool = False,
                          create_missing: bool = False) -> Dict:
    """用高德 POI（类型 150500 地铁站）**校正站点坐标**，可选补录缺失站点与线路。

    为什么不用 `/v3/bus/linename`：实测该接口对深圳地铁返回 0 条（7 种参数组合均如此），
    而 POI 检索能给出坐标，且 `address` 里直接包含所属线路。

    为什么默认 `create_missing=False`：
    实测高德 POI 分页最多只能取到约 225 个站点（少于真实的 351 个），
    而且会把**在建线路**（15/17/19号线等）也带进来。
    因此定位是"**以静态数据为准，高德只负责把坐标校准得更准**"：
    静态数据提供完整的线路与站点，高德提供与路径规划同源的精确坐标。
    """
    if not getattr(amap, "available", False):
        return {"success": False, "message": "未配置 AMAP_WEB_KEY，跳过同步",
                "stations": 0, "withCoord": 0, "lines": 0, "errors": []}

    poi_map: Dict[str, dict] = {}
    errors: List[str] = []

    for page in range(1, max_pages + 1):
        try:
            payload = amap._get("/v3/place/text", {
                "city": city, "types": AMAP_METRO_TYPE,
                "offset": page_size, "page": page, "extensions": "base",
            }, "place/text")
        except Exception as e:
            errors.append(f"第{page}页: {type(e).__name__}: {e}")
            break

        pois = payload.get("pois") or []
        for poi in pois:
            name = _clean_station_name(poi.get("name") or "")
            location = poi.get("location") or ""
            if not name or "," not in location:
                continue
            try:
                lng_str, lat_str = location.split(",", 1)
                lng, lat = float(lng_str), float(lat_str)
            except ValueError:
                continue
            key = station_match_key(name)
            if key and key not in poi_map:
                poi_map[key] = {
                    "name": name, "lng": lng, "lat": lat,
                    "lines": _parse_lines_from_address(poi.get("address") or ""),
                }

        if len(pois) < page_size:
            break

    if not poi_map:
        return {"success": False,
                "message": f"高德未返回 {city} 的地铁站 POI",
                "stations": 0, "withCoord": 0, "lines": 0, "errors": errors}

    station_cache = {s.name: s for s in db.query(MetroStation).filter(
        MetroStation.city == city)}
    key_index = {station_match_key(s.name): s for s in station_cache.values()}
    line_cache = {l.name: l for l in db.query(MetroLine).filter(
        MetroLine.city == city)}

    updated_coords = 0
    created_stations = 0
    created_lines = 0
    links_created = 0
    unmatched = 0

    for key, info in poi_map.items():
        station = key_index.get(key)
        if station is None:
            if not create_missing:
                unmatched += 1
                continue
            station = MetroStation(city=city, name=info["name"])
            db.add(station)
            db.flush()
            station_cache[info["name"]] = station
            key_index[key] = station
            created_stations += 1

        # 高德坐标是 GCJ-02，与路径规划同源，优先采用
        if station.lng is None or overwrite:
            station.lng, station.lat = info["lng"], info["lat"]
            station.coord_source = "amap"
            updated_coords += 1

        if not create_missing:
            # 只校准已有静态数据的坐标，不改动线路归属
            continue

        for line_name in info["lines"]:
            line = line_cache.get(line_name)
            if line is None:
                line = MetroLine(city=city, name=line_name, source="amap",
                                 sort_order=_line_sort_key(line_name))
                db.add(line)
                db.flush()
                line_cache[line_name] = line
                created_lines += 1

            exists = db.query(MetroLineStation).filter(
                MetroLineStation.line_id == line.id,
                MetroLineStation.station_id == station.id).first()
            if exists is None:
                db.add(MetroLineStation(line_id=line.id, station_id=station.id, seq=0))
                links_created += 1

    db.commit()

    return {
        "success": True,
        "message": f"高德返回 {len(poi_map)} 个站点，校准 {updated_coords} 个坐标"
                   + (f"，新增站点 {created_stations}、线路 {created_lines}"
                      if create_missing else
                      f"，未匹配静态数据 {unmatched} 个（已忽略，避免引入在建线路）"),
        "poiStations": len(poi_map),
        "updatedCoords": updated_coords,
        "createdStations": created_stations,
        "createdLines": created_lines,
        "links": links_created,
        "unmatched": unmatched,
        "errors": errors,
    }


def _line_sort_key(name: str) -> int:
    """按线路号排序：1号线=1，14号线=14，非数字的排后面"""
    match = re.match(r"^(\d+)", name or "")
    return int(match.group(1)) if match else 999


def _assign_line_sequence(db: Session, city: str) -> None:
    """给同一线路内的站点排一个稳定顺序（按纬度高→低，仅用于列表展示）"""
    lines = db.query(MetroLine).filter(MetroLine.city == city).all()
    for line in lines:
        links = db.query(MetroLineStation).filter(
            MetroLineStation.line_id == line.id).all()
        if not links:
            continue
        station_map = {s.id: s for s in db.query(MetroStation).filter(
            MetroStation.city == city).all()}
        ordered = sorted(
            links,
            key=lambda link: (
                -(station_map[link.station_id].lat or 0),
                station_map[link.station_id].lng or 0,
            ),
        )
        for index, link in enumerate(ordered, start=1):
            link.seq = index
    db.commit()


def refresh_coords_from_amap(db: Session, city: str, amap,
                             line_names: Optional[List[str]] = None,
                             overwrite: bool = False) -> Dict:
    """兼容入口：现在走 POI 同步（线路名参数保留但不再用于拉取）"""
    return refresh_from_amap_poi(db, city, amap, overwrite=overwrite)


# ---------- 查询 ----------

def list_lines(db: Session, city: str) -> List[dict]:
    ensure_seeded(db, city)
    lines = db.query(MetroLine).filter(
        MetroLine.city == city, MetroLine.status == "operating"
    ).order_by(MetroLine.sort_order, MetroLine.name).all()

    result = []
    for line in lines:
        station_count = db.query(func.count(MetroLineStation.id)).filter(
            MetroLineStation.line_id == line.id).scalar() or 0
        with_coord = db.query(func.count(MetroLineStation.id)).join(
            MetroStation, MetroStation.id == MetroLineStation.station_id
        ).filter(MetroLineStation.line_id == line.id,
                 MetroStation.lng.isnot(None)).scalar() or 0
        result.append({
            "id": line.id,
            "name": line.name,
            "alias": line.alias,
            "color": line.color,
            "sortOrder": line.sort_order,
            "stationCount": station_count,
            "stationWithCoord": with_coord,
            "source": line.source,
        })
    return result


def list_stations(db: Session, city: str, line_name: Optional[str] = None,
                  keyword: Optional[str] = None) -> List[dict]:
    ensure_seeded(db, city)

    query = db.query(MetroStation, MetroLineStation, MetroLine).join(
        MetroLineStation, MetroLineStation.station_id == MetroStation.id
    ).join(MetroLine, MetroLine.id == MetroLineStation.line_id).filter(
        MetroStation.city == city)

    if line_name and line_name not in ("all", "全部"):
        query = query.filter(MetroLine.name == line_name)
    if keyword:
        query = query.filter(MetroStation.name.contains(keyword))

    query = query.order_by(MetroLine.sort_order, MetroLineStation.seq)

    merged: Dict[str, dict] = {}
    for station, link, line in query.all():
        item = merged.get(station.name)
        if item is None:
            item = {
                "id": station.id,
                "name": station.name,
                "city": station.city,
                "lng": station.lng,
                "lat": station.lat,
                "coordSource": station.coord_source,
                "lines": [],
            }
            merged[station.name] = item
        item["lines"].append({"name": line.name, "color": line.color, "seq": link.seq})

    return list(merged.values())


def get_station(db: Session, city: str, name: str) -> Optional[MetroStation]:
    return db.query(MetroStation).filter(
        MetroStation.city == city, MetroStation.name == name).first()


def metro_stats(db: Session, city: str) -> dict:
    lines = db.query(func.count(MetroLine.id)).filter(MetroLine.city == city).scalar() or 0
    stations = db.query(func.count(MetroStation.id)).filter(
        MetroStation.city == city).scalar() or 0
    with_coord = db.query(func.count(MetroStation.id)).filter(
        MetroStation.city == city, MetroStation.lng.isnot(None)).scalar() or 0
    return {"lines": lines, "stations": stations, "stationsWithCoord": with_coord}
