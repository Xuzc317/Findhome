"""高德地图 Web 服务封装

用到的接口（全部需要「Web服务」类型的 Key，与前端 JS Key 不同）：
- 地理编码  /v3/geocode/geo            地址 → 坐标 + 结构化地址 + 匹配级别
- 关键字搜索 /v3/place/text            小区/地铁站等 POI → 坐标
- 周边搜索  /v3/place/around          以坐标为中心找 POI
- 步行路径  /v3/direction/walking      两点间真实步行距离与耗时
- 公交线路  /v3/bus/linename           地铁线路走向与沿途站点（用于同步站点坐标）

设计原则：
1. 没有配置 Key 时**不发起请求**，抛出 AmapKeyMissing，由上层降级处理；
2. 所有响应做缓存（内存 + 可选落库），避免重复消耗配额；
3. 高德返回的 infocode 单独解析，把"配额耗尽/Key 无效"这类问题
   和"地址查不到"区分开，便于如实上报；
4. 不伪造任何坐标：查不到就返回 None。
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import httpx

from backend.config import get_settings, is_configured

BASE_URL = "https://restapi.amap.com"

# 高德常见 infocode 说明（用于把失败原因说清楚）
INFOCODE_MESSAGES = {
    "10000": "请求成功",
    "10001": "Key 不正确或已过期",
    "10003": "访问过于频繁（触发日/秒级配额限制）",
    "10004": "每日访问量已达上限",
    "10009": "请求 Key 与绑定平台不符（该 Key 可能不是 Web服务 类型）",
    "10012": "权限不足，服务未开通",
    "20800": "规划点不在中国境内",
    "20802": "无法规划处路径（起终点过近或不可步行到达）",
    "20803": "起点或终点坐标错误",
}


class AmapError(RuntimeError):
    """高德接口返回错误"""

    def __init__(self, infocode: str, info: str, api: str):
        self.infocode = infocode
        self.info = info
        self.api = api
        friendly = INFOCODE_MESSAGES.get(infocode, info)
        super().__init__(f"[{api}] 高德返回 {infocode}: {friendly}")


class AmapKeyMissing(AmapError):
    """未配置高德 Web 服务 Key"""

    def __init__(self, api: str = ""):
        self.infocode = "no_key"
        self.info = "未配置 AMAP_WEB_KEY"
        self.api = api
        RuntimeError.__init__(
            self,
            "未配置高德 Web 服务 Key（AMAP_WEB_KEY）。"
            "请在 https://console.amap.com 创建「Web服务」类型的 Key 并填入 .env",
        )


@dataclass
class GeoResult:
    """地理编码结果"""
    lng: float
    lat: float
    formatted_address: str = ""
    level: str = ""          # 省/市/区/开发区/乡镇/村庄/兴趣点/门牌号 等
    raw: dict = field(default_factory=dict)

    @property
    def precision(self) -> str:
        """把高德的 level 映射成我们自己的精度档位"""
        level = self.level or ""
        if any(k in level for k in ("门牌", "兴趣点", "POI")):
            return "building"
        if any(k in level for k in ("村庄", "乡镇", "街道")):
            return "community"
        if "区" in level or "开发区" in level:
            return "district"
        if "市" in level or "省" in level:
            return "district"
        return "unknown"


@dataclass
class PoiResult:
    """POI 结果"""
    name: str
    lng: float
    lat: float
    address: str = ""
    poi_type: str = ""
    distance_m: Optional[int] = None
    raw: dict = field(default_factory=dict)


@dataclass
class WalkingResult:
    """步行路径结果"""
    distance_m: int
    duration_s: int
    raw: dict = field(default_factory=dict)

    @property
    def minutes(self) -> int:
        """向上取整到分钟，避免把 90 秒说成 1 分钟"""
        return max(1, (self.duration_s + 59) // 60)


class AmapClient:
    """高德 Web 服务客户端（同步实现，供脚本与后台任务使用）"""

    def __init__(self, key: Optional[str] = None, cache_size: int = 4096,
                 timeout: float = 12.0):
        settings = get_settings()
        self.key = (key if key is not None else settings.amap_web_key or "").strip()
        self.timeout = timeout
        self._cache: Dict[str, object] = {}
        self._cache_size = cache_size
        self.calls = 0                 # 真实请求次数（缓存命中不计）
        self.cache_hits = 0
        self.last_error: Optional[str] = None
        self._client = httpx.Client(timeout=timeout)

    # ---------- 基础 ----------

    @property
    def available(self) -> bool:
        """真正配置了可用 Key（占位符不算）"""
        return is_configured(self.key)

    def _cache_key(self, path: str, params: dict) -> str:
        payload = json.dumps({"p": path, "q": params}, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def _get(self, path: str, params: dict, api_name: str):
        if not self.available:
            raise AmapKeyMissing(api_name)

        params = {k: v for k, v in params.items() if v not in (None, "")}
        cache_key = self._cache_key(path, params)
        if cache_key in self._cache:
            self.cache_hits += 1
            return self._cache[cache_key]

        query = {"key": self.key, "output": "json", **params}
        self.calls += 1
        try:
            response = self._client.get(f"{BASE_URL}{path}", params=query)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as e:
            self.last_error = f"网络错误: {type(e).__name__}: {e}"
            raise AmapError("network", str(e), api_name) from e

        infocode = str(payload.get("infocode", ""))
        if infocode != "10000":
            self.last_error = INFOCODE_MESSAGES.get(infocode, payload.get("info", "未知错误"))
            raise AmapError(infocode, str(payload.get("info", "")), api_name)

        if len(self._cache) >= self._cache_size:
            self._cache.clear()
        self._cache[cache_key] = payload
        return payload

    @staticmethod
    def _to_lnglat(location: str) -> Optional[Tuple[float, float]]:
        """高德返回的 '经度,纬度' 字符串 → (lng, lat)"""
        if not location or "," not in location:
            return None
        try:
            lng_str, lat_str = location.split(",", 1)
            return float(lng_str), float(lat_str)
        except (TypeError, ValueError):
            return None

    # ---------- 地理编码 ----------

    def geocode(self, address: str, city: str = "") -> Optional[GeoResult]:
        """地址 → 坐标。查不到返回 None（不猜测）"""
        if not address:
            return None
        payload = self._get("/v3/geocode/geo",
                            {"address": address, "city": city or None},
                            "geocode")
        geocodes = payload.get("geocodes") or []
        if not geocodes:
            return None

        item = geocodes[0]
        lnglat = self._to_lnglat(item.get("location", ""))
        if not lnglat:
            return None

        return GeoResult(
            lng=lnglat[0], lat=lnglat[1],
            formatted_address=item.get("formatted_address", ""),
            level=item.get("level", ""),
            raw=item,
        )

    def reverse_geocode(self, lng: float, lat: float) -> Optional[dict]:
        """坐标 → 地址（用于校验定位是否落在合理位置）"""
        payload = self._get("/v3/geocode/regeo",
                            {"location": f"{lng:.6f},{lat:.6f}",
                             "extensions": "base"},
                            "regeo")
        regeocode = payload.get("regeocode") or {}
        if not regeocode:
            return None
        component = regeocode.get("addressComponent") or {}
        return {
            "formatted_address": regeocode.get("formatted_address", ""),
            "district": component.get("district", ""),
            "city": component.get("city", "") or component.get("province", ""),
            "raw": regeocode,
        }

    # ---------- POI 搜索 ----------

    def place_text(self, keywords: str, city: str = "", types: str = "",
                   page_size: int = 10) -> List[PoiResult]:
        """关键字搜索 POI（小区、地铁站、写字楼等）"""
        if not keywords:
            return []
        payload = self._get("/v3/place/text",
                            {"keywords": keywords, "city": city or None,
                             "types": types or None, "offset": page_size,
                             "page": 1, "extensions": "base"},
                            "place/text")
        return self._parse_pois(payload)

    def place_around(self, lng: float, lat: float, keywords: str = "",
                     radius: int = 1000, types: str = "",
                     page_size: int = 10) -> List[PoiResult]:
        """周边搜索"""
        payload = self._get("/v3/place/around",
                            {"location": f"{lng:.6f},{lat:.6f}",
                             "keywords": keywords or None, "radius": radius,
                             "types": types or None, "offset": page_size,
                             "page": 1, "extensions": "base"},
                            "place/around")
        return self._parse_pois(payload)

    def _parse_pois(self, payload: dict) -> List[PoiResult]:
        results = []
        for item in payload.get("pois") or []:
            lnglat = self._to_lnglat(item.get("location", ""))
            if not lnglat:
                continue
            distance = item.get("distance")
            try:
                distance_m = int(float(distance)) if distance not in (None, "", []) else None
            except (TypeError, ValueError):
                distance_m = None
            results.append(PoiResult(
                name=item.get("name", ""),
                lng=lnglat[0], lat=lnglat[1],
                address=item.get("address", "") if isinstance(item.get("address"), str) else "",
                poi_type=item.get("type", ""),
                distance_m=distance_m,
                raw=item,
            ))
        return results

    # ---------- 步行路径 ----------

    def walking(self, origin: Tuple[float, float],
                destination: Tuple[float, float]) -> Optional[WalkingResult]:
        """真实步行路径距离与耗时。

        起终点过近/无法步行到达时高德返回 20802，这里返回 None，
        由上层记为 no_route，不用直线距离冒充。
        """
        payload = self._get(
            "/v3/direction/walking",
            {"origin": f"{origin[0]:.6f},{origin[1]:.6f}",
             "destination": f"{destination[0]:.6f},{destination[1]:.6f}"},
            "direction/walking",
        )
        paths = ((payload.get("route") or {}).get("paths")) or []
        if not paths:
            return None

        path = paths[0]
        try:
            distance = int(float(path.get("distance", 0)))
            duration = int(float(path.get("duration", 0)))
        except (TypeError, ValueError):
            return None

        if distance <= 0:
            return None

        return WalkingResult(distance_m=distance, duration_s=duration, raw=path)

    # ---------- 地铁线路 ----------

    def bus_line(self, keywords: str, city: str) -> List[dict]:
        """公交/地铁线路查询，返回含站点的线路列表（用于同步地铁站点）

        高德此接口对地铁线路同样有效，返回 linestr 形如 "1号线(罗湖--机场东)"。
        """
        payload = self._get("/v3/bus/linename",
                            {"keywords": keywords, "city": city,
                             "extensions": "all", "offset": 20, "page": 1},
                            "bus/linename")
        return payload.get("line") or []

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def haversine_meters(lng1: float, lat1: float, lng2: float, lat2: float) -> int:
    """两点直线距离（米），仅作为参考值展示，不作为"实际距离" """
    from math import asin, cos, radians, sin, sqrt

    r = 6371000.0
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = radians(lng2 - lng1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return int(2 * r * asin(sqrt(a)))
