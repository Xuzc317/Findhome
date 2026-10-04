"""地铁线路 / 站点 / 步行距离接口"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from datetime import datetime

from backend.database import get_db
from backend.schemas import (MetroDistanceRequest, MetroSyncRequest,
                             StationDistanceReport, StationUpsertRequest)
from backend.models import StationDistance
from backend.services import metro as metro_service
from backend.services import station_distance
from backend.services.amap import AmapClient, AmapError, AmapKeyMissing

router = APIRouter()

DEFAULT_CITY = "深圳"


@router.get("/metro/lines")
async def list_lines(
    city: str = Query(DEFAULT_CITY, description="城市"),
    db: Session = Depends(get_db),
):
    """地铁线路列表（含站点数与已获取坐标的站点数）"""
    lines = metro_service.list_lines(db, city)
    stats = metro_service.metro_stats(db, city)
    return {"code": 0, "data": lines, "stats": stats}


@router.get("/metro/stations")
async def list_stations(
    city: str = Query(DEFAULT_CITY),
    line: Optional[str] = Query(None, description="线路名，如 1号线；不传=全部"),
    keyword: Optional[str] = Query(None, description="站名关键词"),
    db: Session = Depends(get_db),
):
    """站点列表（按线路分组时可用 stations[].lines 判断换乘）"""
    stations = metro_service.list_stations(db, city, line_name=line, keyword=keyword)
    return {"code": 0, "data": stations, "total": len(stations)}


@router.get("/metro/stats")
async def metro_stats(city: str = Query(DEFAULT_CITY), db: Session = Depends(get_db)):
    return {"code": 0, "data": metro_service.metro_stats(db, city)}


@router.post("/metro/import")
async def import_static_metro(
    city: str = Query(DEFAULT_CITY),
    force: bool = Query(False, description="已存在数据时是否重新导入"),
    db: Session = Depends(get_db),
):
    """从 data/metro/{city}.json 导入线路与站点（幂等）"""
    if force:
        stats = metro_service.import_static(db, city)
    else:
        stats = metro_service.ensure_seeded(db, city)
    return {"code": 0, "success": True, "data": stats.__dict__}


@router.post("/metro/sync-coords")
async def sync_coords(
    request: MetroSyncRequest = Body(default=MetroSyncRequest()),
    db: Session = Depends(get_db),
):
    """用高德线路接口补齐站点坐标（需要 AMAP_WEB_KEY）"""
    city = request.city or DEFAULT_CITY
    metro_service.ensure_seeded(db, city)
    amap = AmapClient()
    try:
        result = metro_service.refresh_coords_from_amap(
            db, city, amap,
            line_names=request.lines,
            overwrite=request.overwrite,
        )
    except AmapKeyMissing as e:
        return {"code": 0, "success": False, "message": str(e),
                "data": {"available": False}}
    except AmapError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        amap.close()

    return {"code": 0, "success": result.get("success", False), **result}


@router.post("/metro/stations/upsert")
async def upsert_station(
    request: StationUpsertRequest = Body(...),
    db: Session = Depends(get_db),
):
    """新增/更新站点坐标

    后端没有「Web服务」Key 时，可用前端 AMap JS API 搜索地铁站后回写。
    """
    from backend.models import MetroLine, MetroLineStation, MetroStation

    station = db.query(MetroStation).filter(
        MetroStation.city == request.city, MetroStation.name == request.name).first()
    created = False
    if station is None:
        station = MetroStation(city=request.city, name=request.name)
        db.add(station)
        db.flush()
        created = True

    if request.lng is not None and request.lat is not None:
        station.lng = float(request.lng)
        station.lat = float(request.lat)
        station.coord_source = request.source

    linked = 0
    for line_name in (request.lines or []):
        line = db.query(MetroLine).filter(
            MetroLine.city == request.city, MetroLine.name == line_name).first()
        if line is None:
            line = MetroLine(city=request.city, name=line_name, source=request.source)
            db.add(line)
            db.flush()
        exists = db.query(MetroLineStation).filter(
            MetroLineStation.line_id == line.id,
            MetroLineStation.station_id == station.id).first()
        if exists is None:
            db.add(MetroLineStation(line_id=line.id, station_id=station.id, seq=0))
            linked += 1

    db.commit()
    return {"code": 0, "success": True,
            "data": {"id": station.id, "name": station.name, "created": created,
                     "lng": station.lng, "lat": station.lat, "linesLinked": linked}}


@router.post("/metro/report-distance")
async def report_distance(
    request: StationDistanceReport = Body(...),
    db: Session = Depends(get_db),
):
    """回写一条步行距离结果（后端高德或浏览器 JS API 均可）"""
    from backend.models import House, MetroStation

    if db.query(House.id).filter(House.id == request.house_id).first() is None:
        raise HTTPException(status_code=404, detail="房源不存在")
    if db.query(MetroStation.id).filter(MetroStation.id == request.station_id).first() is None:
        raise HTTPException(status_code=404, detail="站点不存在")

    record = station_distance.get_cached(db, request.house_id, request.station_id)
    if record is None:
        record = StationDistance(house_id=request.house_id,
                                 station_id=request.station_id)
        db.add(record)

    record.walk_meters = request.walk_meters
    record.walk_minutes = request.walk_minutes
    record.straight_meters = request.straight_meters
    record.status = request.status
    record.message = (request.message or "")[:255] or None
    record.provider = request.provider
    record.computed_at = datetime.now()
    db.commit()

    return {"code": 0, "success": True,
            "data": {"houseId": request.house_id, "stationId": request.station_id,
                     "walkMeters": record.walk_meters, "status": record.status}}


@router.get("/metro/stations/{station_id}/coverage")
async def station_coverage(station_id: str, db: Session = Depends(get_db)):
    """某站点步行距离的计算覆盖情况"""
    return {"code": 0, "data": station_distance.station_coverage(db, station_id)}


@router.post("/metro/stations/{station_id}/distances")
async def compute_distances(
    station_id: str,
    request: MetroDistanceRequest = Body(default=MetroDistanceRequest()),
    db: Session = Depends(get_db),
):
    """计算（增量续算）房源到该站的**真实步行距离**

    可反复调用：已算好的不会重复计算；受 maxCalls 保护，避免一次耗尽高德配额。
    """
    from backend.models import MetroStation

    station = db.query(MetroStation).filter(MetroStation.id == station_id).first()
    if station is None:
        raise HTTPException(status_code=404, detail="站点不存在")

    if station.lng is None or station.lat is None:
        return {
            "code": 0, "success": False,
            "message": f"站点「{station.name}」还没有坐标，请先同步高德地铁数据",
            "data": {"station": station.name, "computed": 0},
        }

    amap = AmapClient()
    try:
        result = station_distance.compute_for_station(
            db, station, amap,
            city=station.city,
            limit=request.limit,
            only_missing=request.only_missing,
            max_amap_calls=request.max_calls,
        )
    except AmapKeyMissing as e:
        return {"code": 0, "success": False, "message": str(e),
                "data": {"available": False}}
    finally:
        amap.close()

    coverage = station_distance.station_coverage(db, station_id)
    return {"code": 0, **result, "coverage": coverage}
