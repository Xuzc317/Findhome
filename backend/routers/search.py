"""通用搜索接口：接收任意查询条件，不再依赖预先写死的需求档案

设计取舍：
- 原来的 `/api/match?profile=longhua` 只能跑一个写死的档案，是"给一个人用"的形态。
  做成产品后，条件必须由请求带来。
- 但"保存搜索"仍然有用（用户不想每次重填），所以档案保留为**可选**功能：
  `/api/search` 走任意条件，`/api/match/profiles` 负责存取档案。
- 两者共用同一个匹配引擎（services/match.py），避免两套逻辑跑偏。
"""

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services import match as match_service
from backend.services.amap import AmapClient, AmapError

router = APIRouter()


class SearchRequest(BaseModel):
    """搜索条件（字段与 Profile 对齐，缺省即"不限"）"""
    city: str = Field("深圳", description="城市（优先选择）")
    stations: List[str] = Field(default_factory=list, description="地铁站名列表")
    line_names: List[str] = Field(default_factory=list, description="按线路选站（与 stations 取并集）")

    max_straight_m: int = Field(1000, description="直线距离上限（米）")
    max_walk_minutes: int = Field(20, description="真实步行时间上限（分钟）")

    price_min: Optional[int] = None
    price_max: Optional[int] = None
    layouts: List[str] = Field(default_factory=list,
                               description="studio/1b1l/2b1l/3b1l/4b+")
    rent_types: List[int] = Field(default_factory=list,
                                  description="出租类型白名单：3整租 4公寓；空=不限")
    exclude_shared: bool = True

    require_elevator: bool = False
    require_precise_location: bool = True
    min_newness_score: Optional[int] = None
    avoid_old_small: bool = True

    sources: List[str] = Field(default_factory=list,
                               description="数据源白名单：xianyu/xiaohongshu/douban/beike")
    listing_kinds: List[str] = Field(default_factory=list,
                                     description="sublet转租/direct个人直租/normal普通")
    poster_types: List[str] = Field(default_factory=list,
                                    description="individual个人房东/agency机构/unknown")
    exclude_agency: bool = False
    sort_by: str = Field("walk", description="walk 步行 / price 价格 / newness 房况")

    compute_walk: bool = Field(True, description="是否计算真实步行距离（较慢，有缓存）")
    max_walk_calls: int = Field(150, description="本次步行计算的调用上限")
    locate_missing: bool = False


@router.post("/search")
async def search(request: SearchRequest = Body(...), db: Session = Depends(get_db)):
    """按任意条件搜索房源

    与 /api/match 的区别：条件来自请求体，而不是预先保存的档案。
    """
    profile = match_service.Profile(
        name="_adhoc",
        city=request.city,
        stations=list(request.stations),
        max_straight_m=request.max_straight_m,
        max_walk_minutes=request.max_walk_minutes,
        price_min=request.price_min,
        price_max=request.price_max,
        layouts=list(request.layouts),
        rent_types=list(request.rent_types),
        exclude_shared=request.exclude_shared,
        require_elevator=request.require_elevator,
        require_precise_location=request.require_precise_location,
        min_newness_score=request.min_newness_score,
        avoid_old_small=request.avoid_old_small,
        sources=list(request.sources),
        listing_kinds=list(request.listing_kinds),
        poster_types=list(request.poster_types),
        exclude_agency=request.exclude_agency,
        sort_by=request.sort_by,
    )

    # 按线路选站：把线路上的站点并入站点清单
    if request.line_names:
        from backend.models import MetroLine, MetroLineStation, MetroStation
        rows = db.query(MetroStation.name).join(
            MetroLineStation, MetroLineStation.station_id == MetroStation.id
        ).join(MetroLine, MetroLine.id == MetroLineStation.line_id).filter(
            MetroStation.city == request.city,
            MetroLine.name.in_(request.line_names),
        ).all()
        merged = list(dict.fromkeys(list(profile.stations) + [r[0] for r in rows]))
        profile.stations = merged

    if not profile.stations:
        raise HTTPException(
            status_code=400,
            detail="请至少选择一个地铁站（或选择一条线路）")

    amap = AmapClient()
    try:
        result = match_service.match(
            db, profile, amap=amap,
            compute_walk=request.compute_walk,
            locate_missing=request.locate_missing,
            max_walk_calls=request.max_walk_calls)
    except AmapError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        amap.close()

    matched = result.get("matched") or []
    pending = result.get("pendingLocation") or []
    return {
        "code": 0,
        "success": result.get("success", True),
        "message": result.get("message"),
        "criteria": profile.to_dict(),
        "stats": result.get("stats"),
        "total": len(matched),
        "data": [m.__dict__ for m in matched],
        "pendingLocation": [m.__dict__ for m in pending],
    }


# 当前实际支持的城市。只保留这两个：其余城市既没有地铁数据、
# 也没有稳定可用的房源来源，列出来只会让用户选了却搜不到东西。
# 新城市接入时同步补这里。
SUPPORTED_CITIES = ["深圳", "北京"]


@router.get("/search/cities")
async def search_cities(db: Session = Depends(get_db)):
    """可选城市（含各地铁线路数与在租房源数），供"城市优先选择"使用"""
    from sqlalchemy import func

    from backend.models import House, MetroLine, MetroStation

    house_rows = dict(db.query(House.city, func.count(House.id)).group_by(House.city).all())
    station_rows = dict(db.query(MetroStation.city, func.count(MetroStation.id))
                        .group_by(MetroStation.city).all())
    line_rows = dict(db.query(MetroLine.city, func.count(MetroLine.id))
                     .group_by(MetroLine.city).all())

    cities = []
    for city in SUPPORTED_CITIES:
        cities.append({
            "name": city,
            "houseCount": house_rows.get(city, 0),
            "stationCount": station_rows.get(city, 0),
            "lineCount": line_rows.get(city, 0),
        })
    cities.sort(key=lambda c: -c["houseCount"])
    return {"code": 0, "data": cities}
