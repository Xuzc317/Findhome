"""房源标记（收藏 / 已联系 / 不感兴趣 / 备注）

这些是**用户自己的数据**，与平台采集数据分开存：采集会覆盖更新 House，
但"我收藏了它"必须长期保存，不随采集或房源下架而丢失。
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import House, HouseMark

router = APIRouter()


class MarkRequest(BaseModel):
    """更新标记。只传需要改的字段，其余保持不变。"""
    houseId: str
    favorite: Optional[bool] = None
    contacted: Optional[bool] = None
    hidden: Optional[bool] = None
    note: Optional[str] = None


class BatchMarkRequest(BaseModel):
    houseIds: List[str] = Field(default_factory=list)


def _to_dict(mark: HouseMark) -> dict:
    return {
        "houseId": mark.house_id,
        "favorite": bool(mark.favorite),
        "contacted": bool(mark.contacted),
        "hidden": bool(mark.hidden),
        "note": mark.note or "",
        "updatedAt": mark.updated_at.isoformat() if mark.updated_at else None,
    }


@router.post("/marks")
async def upsert_mark(request: MarkRequest = Body(...), db: Session = Depends(get_db)):
    """新建或更新一条标记（幂等）

    说明：如果所有标记都为 false 且没有备注，记录会被删除而不是留一条空记录，
    避免"标记表"里堆满无意义的行。
    """
    house = db.query(House).filter(House.id == request.houseId).first()
    if house is None:
        # 允许对任意 id 打标（例如房源已被清理），但提示出来
        pass

    mark = db.query(HouseMark).filter(HouseMark.house_id == request.houseId).first()
    if mark is None:
        mark = HouseMark(house_id=request.houseId)
        db.add(mark)

    if request.favorite is not None:
        mark.favorite = 1 if request.favorite else 0
    if request.contacted is not None:
        mark.contacted = 1 if request.contacted else 0
    if request.hidden is not None:
        mark.hidden = 1 if request.hidden else 0
    if request.note is not None:
        mark.note = request.note[:2000] or None

    db.commit()
    db.refresh(mark)

    empty = not (mark.favorite or mark.contacted or mark.hidden or mark.note)
    if empty:
        db.delete(mark)
        db.commit()
        return {"code": 0, "data": None, "message": "已清空标记"}

    return {"code": 0, "data": _to_dict(mark)}


@router.post("/marks/batch")
async def batch_marks(request: BatchMarkRequest = Body(...),
                      db: Session = Depends(get_db)):
    """批量取标记（结果页一次拿全，避免逐条请求）"""
    ids = [i for i in request.houseIds if i][:500]
    if not ids:
        return {"code": 0, "data": {}}
    rows = db.query(HouseMark).filter(HouseMark.house_id.in_(ids)).all()
    return {"code": 0, "data": {m.house_id: _to_dict(m) for m in rows}}


@router.get("/marks")
async def list_marks(
    filter: str = Query("all", description="all / favorite / contacted / hidden / noted"),
    with_house: bool = Query(True, description="是否连带返回房源基本信息"),
    db: Session = Depends(get_db),
):
    """我的标记列表（默认返回收藏夹视图所需数据）"""
    query = db.query(HouseMark)
    if filter == "favorite":
        query = query.filter(HouseMark.favorite == 1)
    elif filter == "contacted":
        query = query.filter(HouseMark.contacted == 1)
    elif filter == "hidden":
        query = query.filter(HouseMark.hidden == 1)
    elif filter == "noted":
        query = query.filter(HouseMark.note.isnot(None))

    marks = query.order_by(HouseMark.updated_at.desc()).limit(500).all()
    items: List[dict] = []
    if with_house and marks:
        houses = {h.id: h for h in db.query(House).filter(
            House.id.in_([m.house_id for m in marks])).all()}
        for mark in marks:
            data = _to_dict(mark)
            house = houses.get(mark.house_id)
            if house is not None:
                import json as _json
                data["house"] = {
                    "id": house.id,
                    "title": house.title,
                    "price": house.price,
                    "source": house.source,
                    "sourceUrl": house.source_url,
                    "city": house.city,
                    "district": house.district,
                    "community": house.community,
                    "layoutKey": house.layout_key,
                    "pictures": (_json.loads(house.images)
                                 if house.images and house.images != "[]" else []),
                }
            items.append(data)
    else:
        items = [_to_dict(m) for m in marks]
    return {"code": 0, "data": items, "total": len(items)}


@router.delete("/marks/{house_id}")
async def delete_mark(house_id: str, db: Session = Depends(get_db)):
    mark = db.query(HouseMark).filter(HouseMark.house_id == house_id).first()
    if mark is None:
        return {"code": 0, "success": True, "message": "本就没有标记"}
    db.delete(mark)
    db.commit()
    return {"code": 0, "success": True}
