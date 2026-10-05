"""统一配置与集成状态

把散落各处的配置（高德 Key、大模型 Key、各平台 Cookie、数据源可用性）
收敛到一个地方对外暴露，并**统一做密钥脱敏**。

设计原则：
- 对外只回答"**是否已配置 / 是否可用**"，以及给前端用的**非敏感**配置
  （如高德 JS Key 必须下发到浏览器，这是它本来的用法）
- 后端自用的服务端 Key（高德 Web 服务 Key、大模型 Key）**绝不下发**，
  只返回布尔状态与掩码，避免前端或日志无意间把它们带出去
- Cookie 同理：只报告"已配置 / 未配置 / 平台是否接受"，不返回内容
"""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.config import get_settings, is_configured, looks_like_placeholder

# 数据源展示名与说明（含当前实测可用性，供前端展示"哪些源能用"）
SOURCE_INFO: Dict[str, dict] = {
    "xianyu": {
        "name": "闲鱼",
        "access": "browser",
        "note": "搜索接口需页面签名，通过真实浏览器采集；宣传图/中介较多",
    },
    "xiaohongshu": {
        "name": "小红书",
        "access": "browser",
        "note": "搜索页可用，笔记详情页被平台限制；转租类信息密度高",
    },
    "douban": {
        "name": "豆瓣",
        "access": "http",
        "note": "登录后可用；深圳房源多集中在宝安/南山",
    },
    "beike": {
        "name": "贝壳找房",
        "access": "disabled",
        "note": "已放弃：登录/验证码对自动化过于严格，不做绕过",
    },
}


def _mask(value: Optional[str], head: int = 4, tail: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= head + tail:
        return "*" * len(value)
    return f"{value[:head]}{'*' * 8}{value[-tail:]}"


def integration_status() -> dict:
    """各集成的配置状态（不含任何密钥明文，除前端必须的 JS Key）"""
    s = get_settings()

    # 高德：两类 Key 用途不同，分别报告
    web_key = s.amap_web_key if is_configured(s.amap_web_key) else ""
    js_key = s.amap_key if is_configured(s.amap_key) else ""
    security = s.amap_security_code if is_configured(s.amap_security_code) else ""

    # 大模型：两家互为兜底
    deepseek = s.deepseek_api_key if is_configured(s.deepseek_api_key) else ""
    doubao = s.doubao_api_key if is_configured(s.doubao_api_key) else ""

    cookies = {
        "xianyu": s.xianyu_cookie if is_configured(s.xianyu_cookie) else "",
        "xiaohongshu": s.xiaohongshu_cookie if is_configured(s.xiaohongshu_cookie) else "",
        "douban": s.douban_cookie if is_configured(s.douban_cookie) else "",
        "beike": s.beike_cookie if is_configured(s.beike_cookie) else "",
    }

    sources: List[dict] = []
    for key, info in SOURCE_INFO.items():
        sources.append({
            "key": key,
            "name": info["name"],
            "access": info["access"],
            "note": info["note"],
            "enabled": info["access"] != "disabled",
            "cookieConfigured": bool(cookies[key]),
        })

    return {
        "amap": {
            # 前端地图需要（这是 JS Key 的正常用法）
            "jsKey": js_key,
            "jsSecurityCode": security,
            "jsConfigured": bool(js_key),
            # 服务端自用，绝不下发明文
            "webServiceConfigured": bool(web_key),
            "webServiceMasked": _mask(web_key),
            "available": bool(web_key),
            "note": "两类 Key 不通用；Web 服务 Key 用于地理编码/POI/步行路径，JS Key 用于前端地图",
        },
        "llm": {
            "provider": s.llm_provider,
            "deepseekConfigured": bool(deepseek),
            "doubaoConfigured": bool(doubao),
            "available": bool(deepseek or doubao),
            "thinking": s.llm_thinking,
            "note": "用于从文字/图片推断房源位置；LLM_PROVIDER=auto 时两家互为兜底",
        },
        "sources": sources,
        "cookieImport": {
            "supported": ["xianyu", "xiaohongshu", "douban", "beike"],
            "tools": {
                "browserDaemon": "python browser_daemon.py（扫码登录并保持会话）",
                "exportCookies": "python export_cookies.py（从常驻浏览器导出到 .env）",
                "importCookie": "python import_cookie.py <平台>（手工粘贴并校验）",
            },
            "note": "只接受本人浏览器登录态；不处理密码，不绕过验证码",
        },
    }


def public_config() -> dict:
    """前端启动所需的配置（保持原 /api/config 的兼容字段）"""
    s = get_settings()
    js_key = s.amap_key if is_configured(s.amap_key) else ""
    security = s.amap_security_code if is_configured(s.amap_security_code) else ""
    return {
        "amapKey": js_key,
        "amapSecurityCode": security,
        "amapConfigured": bool(js_key),
        "commuteDestination": s.commute_destination,
        "commuteDestinationLng": s.commute_destination_lng,
        "commuteDestinationLat": s.commute_destination_lat,
    }
