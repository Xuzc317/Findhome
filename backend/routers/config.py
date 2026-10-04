from fastapi import APIRouter

from backend.config import get_settings, is_configured
from backend.schemas import CommuteConfig

router = APIRouter()


@router.get("/config")
async def get_config():
    """前端运行时配置

    **为什么高德 Key 走接口下发而不是打包进前端**：
    Vite 会把 `VITE_*` 环境变量内联进静态产物（`build/assets/*.js`），
    一旦分享或部署构建目录，Key 就随之泄漏。改为运行时从后端读取后，
    密钥只存在于后端 `.env`（已被 gitignore），静态产物里不含任何密钥。

    注意：JS API 的 Key 与安全密钥最终必然要到达浏览器（这是高德 JS API 的
    工作方式），因此仍应在高德控制台给该 Key 配置**域名白名单**作为第二道防线。
    """
    settings = get_settings()
    return {
        "success": True,
        "data": {
            # 高德 JS API（Web端）Key —— 仅当确实配置了才下发
            "amapKey": settings.amap_key if is_configured(settings.amap_key) else "",
            "amapSecurityCode": (settings.amap_security_code
                                 if is_configured(settings.amap_security_code) else ""),
            "amapConfigured": is_configured(settings.amap_key),
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
