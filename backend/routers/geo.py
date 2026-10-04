"""地理定位与房型回填接口

定位是"有成本的慢操作"：需要调用高德、可选调用大模型。
因此接口设计成**小批量 + 可反复调用**，前端可以显示进度、随时中断。
"""

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.models import House, StationDistance
from backend.schemas import (GeoLocateRequest, GeoReportRequest,
                             LayoutBackfillRequest)
from backend.services import geolocate as geolocate_service
from backend.services import layout as layout_service
from backend.services.amap import AmapClient, AmapError
from backend.services.llm import LLMClient

router = APIRouter()

DEFAULT_CITY = "深圳"


@router.get("/geo/config")
async def geo_config():
    """定位相关能力状态：高德是否可用、大模型是否可用"""
    amap = AmapClient()
    llm = LLMClient()
    try:
        return {
            "code": 0,
            "data": {
                "amap": {"available": amap.available},
                "llm": llm.describe_config(),
                "layoutOptions": layout_service.LAYOUT_OPTIONS,
            },
        }
    finally:
        amap.close()
        llm.close()


@router.get("/geo/stats")
async def geo_stats(city: str = Query(DEFAULT_CITY), db: Session = Depends(get_db)):
    """定位覆盖率：按来源与精度统计，便于判断还有多少房源没定位"""
    total = db.query(func.count(House.id)).filter(House.city == city).scalar() or 0
    with_coord = db.query(func.count(House.id)).filter(
        House.city == city, House.longitude.isnot(None)).scalar() or 0

    by_source = dict(db.query(House.geo_source, func.count(House.id)).filter(
        House.city == city, House.geo_source.isnot(None)
    ).group_by(House.geo_source).all())

    by_precision = dict(db.query(House.geo_precision, func.count(House.id)).filter(
        House.city == city, House.geo_precision.isnot(None)
    ).group_by(House.geo_precision).all())

    layout_rows = dict(db.query(House.layout_key, func.count(House.id)).filter(
        House.city == city, House.layout_key.isnot(None)
    ).group_by(House.layout_key).all())

    distances = db.query(func.count(StationDistance.id)).filter(
        StationDistance.status == "ok").scalar() or 0

    return {
        "code": 0,
        "data": {
            "city": city,
            "total": total,
            "withCoord": with_coord,
            "withoutCoord": total - with_coord,
            "bySource": by_source,
            "byPrecision": by_precision,
            "byLayout": layout_rows,
            "stationDistancesCached": distances,
            "coveragePercent": round(with_coord / total * 100, 1) if total else 0.0,
        },
    }


@router.post("/geo/locate")
async def locate_batch(
    request: GeoLocateRequest = Body(default=GeoLocateRequest()),
    db: Session = Depends(get_db),
):
    """批量推断房源坐标（小批量、可反复调用）"""
    city = request.city or DEFAULT_CITY
    amap = AmapClient()
    llm = LLMClient()

    if not amap.available:
        amap.close()
        llm.close()
        return {
            "code": 0, "success": False,
            "message": "未配置 AMAP_WEB_KEY，无法推断位置。"
                       "请在 https://console.amap.com 创建「Web服务」类型 Key 并填入 .env",
            "data": {"available": False},
        }

    llm_extract = None
    if request.use_llm and llm.available:
        def llm_extract(house):  # noqa: E306
            text = " ".join(filter(None, [house.title, house.description, house.tags]))
            return llm.extract_location(text, city=house.city or city)

    try:
        result = geolocate_service.locate_batch(
            db, amap, city=city, limit=request.limit,
            only_missing=request.only_missing,
            llm_extract=llm_extract, max_amap_calls=request.max_calls,
        )
    except AmapError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        amap.close()
        llm.close()

    return {"code": 0, "success": True, "data": result,
            "llm": {"used": llm_extract is not None, "active": llm.provider}}


@router.post("/geo/locate/{house_id}")
async def locate_one(
    house_id: str,
    use_llm: bool = Query(True),
    db: Session = Depends(get_db),
):
    """对单条房源推断位置，返回完整推断过程（便于人工核对）"""
    house = db.query(House).filter(House.id == house_id).first()
    if house is None:
        raise HTTPException(status_code=404, detail="房源不存在")

    amap = AmapClient()
    llm = LLMClient()
    if not amap.available:
        amap.close()
        llm.close()
        return {"code": 0, "success": False,
                "message": "未配置 AMAP_WEB_KEY，无法推断位置"}

    llm_extract = None
    if use_llm and llm.available:
        def llm_extract(h):  # noqa: E306
            text = " ".join(filter(None, [h.title, h.description, h.tags]))
            return llm.extract_location(text, city=h.city or DEFAULT_CITY)

    try:
        candidates = geolocate_service.extract_candidates(house)
        outcome = geolocate_service.locate_house(db, house, amap, llm_extract=llm_extract)
    finally:
        amap.close()
        llm.close()

    return {
        "code": 0,
        "success": outcome.success,
        "message": outcome.message,
        "data": {
            "houseId": house.id,
            "title": house.title,
            "candidates": [c.__dict__ for c in candidates],
            "result": {
                "lng": outcome.lng, "lat": outcome.lat,
                "source": outcome.source, "precision": outcome.precision,
                "confidence": outcome.confidence, "query": outcome.query,
                "note": outcome.note,
            },
        },
    }


@router.post("/geo/report")
async def report_location(
    request: GeoReportRequest = Body(...),
    db: Session = Depends(get_db),
):
    """回写一条定位结果

    允许的来源包括后端高德调用与**浏览器端 AMap JS API**：
    如果后端没有「Web服务」Key，可以在前端用 JS API 定位后回写到这里，
    数据同样落到 houses 表并带上来源与精度。
    """
    house = db.query(House).filter(House.id == request.house_id).first()
    if house is None:
        raise HTTPException(status_code=404, detail="房源不存在")

    # 平台原始坐标优先级最高，不允许被推断结果覆盖
    if (house.geo_source or "") == "platform" and request.source != "manual":
        return {"code": 0, "success": False,
                "message": "该房源已有平台坐标，已跳过（如需覆盖请用 source=manual）"}

    house.longitude = float(request.lng)
    house.latitude = float(request.lat)
    house.geo_source = request.source
    house.geo_precision = request.precision
    house.geo_confidence = request.confidence
    house.geo_query = (request.query or "")[:255] or None
    house.geo_note = (request.note or "")[:255] or None
    house.geo_updated_at = datetime.now()
    db.commit()

    return {"code": 0, "success": True,
            "data": {"houseId": house.id, "lng": house.longitude,
                     "lat": house.latitude, "source": house.geo_source,
                     "precision": house.geo_precision}}


@router.post("/geo/backfill-layout")
async def backfill_layout(
    request: LayoutBackfillRequest = Body(default=LayoutBackfillRequest()),
    db: Session = Depends(get_db),
):
    """为历史房源回填房型解析（幂等，可反复执行）"""
    query = db.query(House)
    if request.city:
        query = query.filter(House.city == request.city)
    if request.only_missing:
        query = query.filter(House.layout_key.is_(None))
    houses = query.limit(request.limit).all()

    updated = 0
    stats = {}
    for house in houses:
        result = layout_service.parse_layout(
            house.title, house.description,
            rent_type=house.rent_type or 0, room_type=house.room_type)
        if result.layout_key is None:
            continue
        house.bedrooms = result.bedrooms
        house.living_rooms = result.living_rooms
        house.layout_key = result.layout_key
        house.layout_confidence = result.confidence
        house.layout_evidence = (result.evidence or "")[:255] or None
        stats[result.layout_key] = stats.get(result.layout_key, 0) + 1
        updated += 1

    db.commit()
    return {"code": 0, "success": True,
            "data": {"scanned": len(houses), "updated": updated, "byLayout": stats}}
