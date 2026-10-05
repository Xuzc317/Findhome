"""按需采集任务接口

流程：POST /tasks/collect 启动 → 轮询 GET /tasks/{id} 看进度 → 完成后结果在
同一响应里返回（result 字段）。长任务不阻塞 HTTP 请求。
"""

from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services import collect_task

router = APIRouter()


class CollectRequest(BaseModel):
    """采集 + 筛选条件（字段与搜索接口对齐，另加采集范围控制）"""
    city: str = "深圳"
    stations: List[str] = Field(default_factory=list)
    line_names: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=lambda: ["xianyu", "xiaohongshu", "douban"])

    price_min: Optional[int] = None
    price_max: Optional[int] = None
    layouts: List[str] = Field(default_factory=list)
    rent_types: List[int] = Field(default_factory=list)
    exclude_shared: bool = True

    max_straight_m: int = 1000
    max_walk_minutes: int = 20
    require_elevator: bool = False
    require_precise_location: bool = True
    avoid_old_small: bool = True

    listing_kinds: List[str] = Field(default_factory=list)
    poster_types: List[str] = Field(default_factory=list)
    exclude_agency: bool = False
    sort_by: str = "walk"

    compute_walk: bool = True
    max_walk_calls: int = 150
    locate_limit: int = 200
    # 每个站要搜多少个关键词后缀 × 平台；站点越多耗时越长，所以默认限 6 个站
    max_stations: int = 6
    cdp_port: int = 9222


@router.post("/tasks/collect")
async def start_collect(request: CollectRequest = Body(...)):
    """启动一次"实时采集 + 筛选"任务，立即返回 taskId"""
    criteria = request.model_dump()

    # 按线路展开站点（与搜索接口一致）
    if request.line_names:
        from backend.database import SessionLocal
        from backend.models import MetroLine, MetroLineStation, MetroStation
        db = SessionLocal()
        try:
            rows = db.query(MetroStation.name).join(
                MetroLineStation, MetroLineStation.station_id == MetroStation.id
            ).join(MetroLine, MetroLine.id == MetroLineStation.line_id).filter(
                MetroStation.city == request.city,
                MetroLine.name.in_(request.line_names),
            ).all()
            merged = list(dict.fromkeys(
                list(criteria["stations"]) + [r[0] for r in rows]))
            criteria["stations"] = merged
        finally:
            db.close()

    if not criteria["stations"]:
        raise HTTPException(status_code=400, detail="请至少选择一个地铁站或一条线路")

    task = collect_task.create_task(criteria)
    collect_task.start_task(task)
    return {"code": 0, "data": task.to_dict()}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str,
                          include_result: bool = Query(True)):
    """查询任务进度；完成后同一响应里带 result"""
    task = collect_task.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return {"code": 0, "data": task.to_dict(include_result=include_result)}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    task = collect_task.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    task.cancel_requested = True
    task.log("已请求取消，将在当前步骤结束后停止")
    return {"code": 0, "data": task.to_dict()}


@router.get("/tasks")
async def list_tasks():
    """最近任务（便于前端恢复进度）"""
    return {"code": 0, "data": []}
