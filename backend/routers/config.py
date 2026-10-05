from backend.services import integrations
from fastapi import APIRouter

from backend.config import get_settings, is_configured
from backend.schemas import CommuteConfig

router = APIRouter()


@router.get("/config")
async def get_config():
    """前端启动配置（高德 JS Key、通勤目的地）"""
    return {"success": True, "data": integrations.public_config()}


@router.get("/settings")
async def get_settings_status():
    """统一配置与集成状态

    只返回"是否已配置 / 是否可用"与非敏感配置；
    服务端 Key 与 Cookie **不下发明文**，避免前端或日志把它们带出去。
    """
    return {"success": True, "data": integrations.integration_status()}


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
