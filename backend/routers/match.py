"""需求匹配接口：按"地铁站 + 预算 + 房型 + 通勤容忍度"挑房"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.schemas import ProfileSaveRequest
from backend.services import match as match_service
from backend.services.amap import AmapClient
from backend.services.amap import AmapError

router = APIRouter()


@router.get("/match/profiles")
async def list_profiles():
    """列出可用的需求档案"""
    import glob
    import os
    files = glob.glob(os.path.join(match_service.PROFILE_DIR, "*.json"))
    data = []
    for path in sorted(files):
        name = os.path.basename(path)[:-5]
        try:
            profile = match_service.Profile.load(name)
            data.append({"name": name, "profile": profile.to_dict()})
        except Exception as e:
            data.append({"name": name, "error": f"{type(e).__name__}: {e}"})
    return {"code": 0, "data": data}


@router.post("/match/profiles")
async def save_profile(request: ProfileSaveRequest = Body(...)):
    """新建/更新需求档案（便于前端保存"我的通勤条件"）"""
    profile = match_service.Profile(
        name=request.name,
        city=request.city,
        stations=request.stations,
        max_straight_m=request.max_straight_m,
        max_walk_minutes=request.max_walk_minutes,
        price_min=request.price_min,
        price_max=request.price_max,
        layouts=request.layouts,
        rent_types=request.rent_types,
        exclude_shared=request.exclude_shared,
        require_elevator=request.require_elevator,
        require_precise_location=request.require_precise_location,
        min_newness_score=request.min_newness_score,
        avoid_old_small=request.avoid_old_small,
        sources=request.sources,
        listing_kinds=request.listing_kinds,
        poster_types=request.poster_types,
        exclude_agency=request.exclude_agency,
        sort_by=request.sort_by,
        notes=request.notes,
    )
    path = profile.save()
    return {"code": 0, "success": True, "data": {"path": path,
                                                 "profile": profile.to_dict()}}


@router.get("/match")
async def run_match(
    profile: str = Query("longhua", description="需求档案名"),
    walk: bool = Query(True, description="是否计算真实步行距离（较慢）"),
    locate: bool = Query(False, description="是否顺带定位缺坐标的候选"),
    max_walk_calls: int = Query(120, description="本次步行计算的调用上限"),
    db: Session = Depends(get_db),
):
    """按需求档案匹配房源，返回逐条"为什么符合"

    注意：`walk=true` 且存在未计算的房源时会调用高德步行规划，
    首次可能较慢；结果会落库缓存，后续查询很快。
    """
    try:
        prof = match_service.Profile.load(profile)
    except FileNotFoundError:
        raise HTTPException(status_code=404,
                            detail=f"需求档案不存在: {profile}（见 /api/match/profiles）")

    amap = AmapClient()
    try:
        result = match_service.match(
            db, prof, amap=amap, compute_walk=walk,
            locate_missing=locate, max_walk_calls=max_walk_calls)
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
        "profile": result.get("profile"),
        "stats": result.get("stats"),
        "total": len(matched),
        "data": [m.__dict__ for m in matched],
        # 位置待确认的单独一栏。这里曾经漏掉过，导致前端那个 Tab 永远是空的
        # （角标数字来自 stats 所以看着正常，列表却是 undefined）。
        "pendingLocation": [m.__dict__ for m in pending],
        "report": match_service.render_report(result),
    }
