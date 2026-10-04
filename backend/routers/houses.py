from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models import House
from backend.schemas import (
    HouseResponse, HouseSearchParams, HouseSearchResponse,
    MapHouseItem, MapHouseQuery
)
from backend.services.search import HouseSearchService
from backend.services.risk import RiskScorer
from backend.services.dedup import DedupService
import json

router = APIRouter()


@router.get("/v3/houses")
async def get_houses(
    city: Optional[str] = Query(None, description="城市"),
    district: Optional[str] = Query(None, description="行政区"),
    source: Optional[str] = Query(None, description="数据源"),
    keyword: Optional[str] = Query(None, description="关键词"),
    keyword_exclude: Optional[str] = Query(None, description="排除关键词"),
    # 价格：同时兼容下划线与前端 camelCase 两种写法
    from_price: Optional[int] = Query(None, description="最低价格"),
    fromPrice: Optional[int] = Query(None, description="最低价格(camelCase)"),
    to_price: Optional[int] = Query(None, description="最高价格"),
    toPrice: Optional[int] = Query(None, description="最高价格(camelCase)"),
    rent_type: Optional[int] = Query(None, description="租房类型: -1全部 0未知 1合租 2单间 3整租 4公寓"),
    rentType: Optional[int] = Query(None, description="租房类型(camelCase)"),
    interval_day: Optional[int] = Query(None, description="最近N天"),
    intervalDay: Optional[int] = Query(None, description="最近N天(camelCase)"),
    page: int = Query(0, ge=0, description="页码(从0开始)"),
    page_size: Optional[int] = Query(None, ge=1, le=500, description="每页数量"),
    pageSize: Optional[int] = Query(None, ge=1, le=500, description="每页数量(camelCase)"),
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sortBy: Optional[str] = Query(None, description="排序字段(camelCase)"),
    sort_order: Optional[str] = Query(None, description="排序方向 asc/desc"),
    sortOrder: Optional[str] = Query(None, description="排序方向(camelCase)"),
    commute_max_duration: Optional[int] = Query(None, description="最大通勤时间(分钟)"),
    max_agent_score: Optional[int] = Query(None, description="最大中介评分"),
    hide_duplicates: bool = Query(True, description="隐藏重复房源"),
    db: Session = Depends(get_db)
):
    """搜索房源列表 (v3 API，兼容前端 House-Map.newUI)

    响应体为 {"code": 0, "data": [...]}，因为前端 base.ts 会在 axios 响应上再取一次 .data。
    """
    params = HouseSearchParams(
        city=city,
        district=district,
        source=source,
        keyword=keyword,
        keyword_exclude=keyword_exclude,
        from_price=from_price if from_price is not None else fromPrice,
        to_price=to_price if to_price is not None else toPrice,
        rent_type=rent_type if rent_type is not None else rentType,
        interval_day=interval_day if interval_day is not None else intervalDay,
        page=page,
        page_size=page_size or pageSize or 20,
        sort_by=sort_by or sortBy or "publish_time",
        sort_order=sort_order or sortOrder or "desc",
        commute_max_duration=commute_max_duration,
        max_agent_score=max_agent_score,
        hide_duplicates=hide_duplicates,
    )

    service = HouseSearchService(db)
    houses, total = service.search(params)

    return {
        "code": 0,
        "data": [_house_to_response(h) for h in houses],
        "total": total,
        "page": params.page,
        "pageSize": params.page_size,
        "hasMore": (params.page + 1) * params.page_size < total,
    }


@router.post("/v2/houses")
async def search_houses_post(
    query: dict,
    db: Session = Depends(get_db)
):
    """房源搜索 POST 接口 (兼容前端地图查询)"""
    service = HouseSearchService(db)
    city = query.get("city", "上海")
    source = query.get("source")
    keyword = query.get("keyword")
    rent_type = query.get("rentType")
    interval_day = query.get("intervalDay", 30)

    houses = service.get_map_houses(
        city=city,
        source=source,
        keyword=keyword,
        rent_type=rent_type,
        interval_day=interval_day,
    )

    return {"success": True, "code": 0, "data": [_house_to_response(h) for h in houses]}


@router.get("/v2/houses/{house_id}")
async def get_house_detail(
    house_id: str,
    onlineURL: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """获取房源详情"""
    service = HouseSearchService(db)
    house = service.get_by_id(house_id)

    if not house and onlineURL:
        # 尝试用URL查找
        house = db.query(House).filter(House.source_url == onlineURL).first()

    if not house:
        return {"code": 404, "success": False, "message": "房源不存在"}

    # 获取风险原因
    reasons = RiskScorer.get_risk_reasons(house)

    data = _house_to_response(house)
    return {"code": 0, "success": True, "data": data, "risk_reasons": reasons}


@router.get("/houses/{house_id}/risk")
async def get_house_risk(
    house_id: str,
    db: Session = Depends(get_db)
):
    """获取房源风险评分详情"""
    service = HouseSearchService(db)
    house = service.get_by_id(house_id)

    if not house:
        return {"success": False, "message": "房源不存在"}

    scores = RiskScorer.score_house(house)
    reasons = RiskScorer.get_risk_reasons(house)

    return {
        "success": True,
        "data": {
            "scores": scores,
            "reasons": reasons,
            "is_high_risk": any(v > 70 for v in scores.values()),
        }
    }


@router.get("/houses/sources/count")
async def get_sources_count(
    city: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """获取各数据源房源数量"""
    service = HouseSearchService(db)
    counts = service.get_sources_count(city)
    return {"success": True, "data": counts}


@router.put("/v2/houses-lat-lng")
async def update_houses_lat_lng(
    items: List[dict] = Body(default=[]),
    db: Session = Depends(get_db)
):
    """批量回填房源经纬度（前端地图校准后调用）"""
    updated = 0
    for item in items or []:
        house_id = item.get("id")
        if not house_id:
            continue
        house = db.query(House).filter(House.id == house_id).first()
        if not house:
            continue
        try:
            if item.get("longitude") not in (None, ""):
                house.longitude = float(item["longitude"])
            if item.get("latitude") not in (None, ""):
                house.latitude = float(item["latitude"])
        except (TypeError, ValueError):
            continue
        updated += 1
    db.commit()
    return {"success": True, "code": 0, "data": {"updated": updated}}


@router.post("/v3/houses/{house_id}/report")
async def report_house(
    house_id: str,
    city: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """举报房源（本地版仅记录状态，不做审核流程）"""
    house = db.query(House).filter(House.id == house_id).first()
    if not house:
        return {"code": 404, "success": False, "message": "房源不存在"}
    return {"code": 0, "success": True, "data": {"id": house_id, "reported": True}}


@router.delete("/v3/houses/{house_id}")
async def delete_house(
    house_id: str,
    city: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """软删除房源（status=1）"""
    house = db.query(House).filter(House.id == house_id).first()
    if not house:
        return {"code": 404, "success": False, "message": "房源不存在"}

    house.status = 1
    db.commit()
    return {"code": 0, "success": True, "data": {"id": house_id, "status": 1}}


# ==================== 内部工具函数 ====================

def _house_to_response(house: House) -> dict:
    """将 House ORM 对象转换为响应字典（兼容前端字段名）"""
    # 解析图片
    pictures = []
    try:
        if house.images:
            parsed = json.loads(house.images)
            if isinstance(parsed, list):
                pictures = parsed
    except Exception:
        pass

    # 生成 icon（按价格分色）
    icon = ""
    if house.price and house.price > 0:
        price_k = house.price // 1000
        colors = ["Blue", "PaleGreen", "LightGreen", "PaleYellow",
                  "OrangeYellow", "PaleRed", "Red", "Pink", "Violet", "Black"]
        icon = colors[min(price_k, len(colors) - 1)]

    # 出租类型显示名
    rent_type_map = {0: "未知", 1: "合租", 2: "单间", 3: "整租", 4: "公寓"}
    display_rent_type = rent_type_map.get(house.rent_type, "未知")

    # 来源显示名
    from backend.constants import display_source
    display_source_name = display_source(house.source)

    ref_time = house.publish_time or house.create_time

    return {
        "id": house.id,
        "title": house.title,
        "text": house.description or "",
        "price": house.price or 0,
        "city": house.city or "",
        "district": house.district or "",
        "location": house.address or house.community or house.area or "",
        "source": house.source,
        "displaySource": display_source_name,
        "source_url": house.source_url,
        "onlineURL": house.source_url,
        "pubTime": house.publish_time.isoformat() if house.publish_time else "",
        "publishDate": house.publish_time.strftime("%Y-%m-%d") if house.publish_time else "",
        "timestamp": int(ref_time.timestamp() * 1000) if ref_time else 0,
        "createTime": house.create_time.isoformat() if house.create_time else "",
        "updateTime": house.update_time.isoformat() if house.update_time else "",
        "rentType": house.rent_type,
        "displayRentType": display_rent_type,
        "longitude": house.longitude,
        "latitude": house.latitude,
        "picURLs": house.images,
        "pictures": pictures if pictures else [""],
        "tags": house.tags or "",
        "labels": house.tags or "",
        "status": house.status,
        "icon": icon,
        "publisher": house.publisher or "",
        "agentScore": house.agent_score,
        "adScore": house.ad_score,
        "suspiciousScore": house.suspicious_score,
        "confidenceScore": house.confidence_score,
        "isDuplicate": house.is_duplicate,
        "commuteDuration": house.commute_duration,
        "commuteDistance": house.commute_distance,
        "reportNum": "0",
    }
