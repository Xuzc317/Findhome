"""城市与行政区接口

兼容原有 HouseSearch 前端（House-Map.newUI）的调用约定：
    GET /api/v2/cities?fields=id,city,sources
    GET /api/v2/cities/{city}/districts

响应体统一为 {"code": 0, "data": ...}，因为前端 base.ts 会在 axios 响应上再取一次 .data。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from backend.constants import DEFAULT_CITIES, DEFAULT_CITY_SOURCES, display_source
from backend.database import get_db
from backend.models import House

router = APIRouter()


@router.get("/v2/cities")
async def list_cities(
    fields: str = None,
    db: Session = Depends(get_db),
):
    """城市列表（含各城市可选数据源）

    - 静态默认城市保证空库时前端筛选栏可用
    - 数据库中已存在房源的城市会自动补充进来
    """
    rows = db.query(House.city, House.source).filter(House.city.isnot(None)).distinct().all()

    city_sources: dict[str, set] = {}
    for city, source in rows:
        if not city:
            continue
        city_sources.setdefault(city, set())
        if source:
            city_sources[city].add(source)

    # 默认城市在前，其余按名称追加
    ordered = list(DEFAULT_CITIES)
    for city in sorted(city_sources.keys()):
        if city not in ordered:
            ordered.append(city)

    data = []
    for index, city in enumerate(ordered, start=1):
        # 该城市实际出现过的数据源 + 默认数据源
        sources = list(DEFAULT_CITY_SOURCES)
        for extra in sorted(city_sources.get(city, set())):
            if extra not in sources:
                sources.append(extra)

        data.append({
            "id": index,
            "city": city,
            "sources": [
                {"source": s, "displaySource": display_source(s)} for s in sources
            ],
        })

    return {"code": 0, "data": data}


@router.get("/v2/cities/{city}/districts")
async def list_districts(city: str, db: Session = Depends(get_db)):
    """城市下的行政区列表（来源于已采集房源）"""
    rows = (
        db.query(House.district)
        .filter(House.city == city, House.district.isnot(None), House.district != "")
        .group_by(House.district)
        .order_by(func.count(House.id).desc())
        .all()
    )
    districts: List[str] = [row[0] for row in rows if row[0]]
    return {"code": 0, "data": districts}
