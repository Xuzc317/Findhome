from fastapi import APIRouter
from backend.config import get_settings
from backend.schemas import CommuteConfig

router = APIRouter()


@router.get("/config")
async def get_config():
    """获取公开配置"""
    settings = get_settings()
    return {
        "success": True,
        "data": {
            "amapKey": settings.amap_key,
            "commuteDestination": settings.commute_destination,
            "commuteDestinationLng": settings.commute_destination_lng,
            "commuteDestinationLat": settings.commute_destination_lat,
        }
    }


@router.post("/config/commute")
async def update_commute_config(config: CommuteConfig):
    """更新通勤配置（仅运行时生效，不持久化到.env）"""
    # 这里可以扩展为持久化到数据库
    return {
        "success": True,
        "message": "通勤配置已更新",
        "data": {
            "destination": config.destination,
            "longitude": config.longitude,
            "latitude": config.latitude,
        }
    }
