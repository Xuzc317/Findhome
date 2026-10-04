"""
数据源爬虫基类
所有平台爬虫都应继承此类并实现抽象方法
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
import httpx

# 联系方式/长数字，必须在提价前剔除，否则手机号会被误当成租金
PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")
CONTACT_PATTERN = re.compile(r"(?:qq|扣扣|微信|vx|v信|wx|电话|手机)\s*[:：]?\s*\d+", re.IGNORECASE)
LONG_DIGIT_PATTERN = re.compile(r"\d{7,}")

# 必须带价格语境的模式（(正则, 是否需要乘 1000)）
PRICE_PATTERNS = [
    (re.compile(r"(\d{3,5})\s*(?:元|块)\s*(?:/?\s*月)?"), False),
    (re.compile(r"(\d{3,5})\s*/\s*月"), False),
    (re.compile(r"月租\s*[:：]?\s*(\d{3,5})"), False),
    (re.compile(r"租金\s*[:：]?\s*(\d{3,5})"), False),
    (re.compile(r"(\d(?:\.\d)?)\s*[kK]\b"), True),
    (re.compile(r"(\d(?:\.\d)?)\s*[kK]\s*(?:/|每)?\s*月"), True),
]

# 兜底：住宅标题里的裸 4-5 位数字基本就是租金（手机号/长数字已在上一步剔除）
BARE_PRICE_PATTERN = re.compile(r"(?<!\d)(\d{4,5})(?!\d)")


def extract_price(text: str, min_price: int = 300, max_price: int = 50000) -> Optional[int]:
    """从文本中保守地提取月租金。

    只接受带有价格语境（元/块//月/月租/租金/k）的数字；
    若都没有，再用排除年份后的裸数字兜底。
    宁可返回 None（前端显示为未知），也不要把手机号、年份、编号当成租金。
    """
    if not text:
        return None

    clean = PHONE_PATTERN.sub(" ", text)
    clean = CONTACT_PATTERN.sub(" ", clean)
    clean = LONG_DIGIT_PATTERN.sub(" ", clean)

    for pattern, is_kilo in PRICE_PATTERNS:
        for match in pattern.finditer(clean):
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            price = int(value * 1000) if is_kilo else int(value)
            if min_price <= price <= max_price:
                return price

    # 兜底：裸数字，但排除 1900-2100 这类明显是年份的数字
    for match in BARE_PRICE_PATTERN.finditer(clean):
        price = int(match.group(1))
        if 1900 <= price <= 2100:
            continue
        if 1000 <= price <= 30000:
            return price

    return None


@dataclass
class RawHouse:
    """原始房源数据（爬虫采集后的中间结构）"""
    source: str
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    area: Optional[str] = None
    community: Optional[str] = None
    address: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    price: Optional[int] = None
    rent_type: int = 0  # 0未知 1合租 2单间 3整租 4公寓
    room_type: Optional[str] = None
    area_size: Optional[float] = None
    orientation: Optional[str] = None
    publish_time: Optional[datetime] = None
    publisher: Optional[str] = None
    publisher_id: Optional[str] = None
    images: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    raw_data: Optional[dict] = None


class BaseCrawler(ABC):
    """爬虫基类"""

    # 子类必须定义
    SOURCE_NAME: str = ""
    DISPLAY_NAME: str = ""
    NEEDS_LOGIN: bool = False

    def __init__(self, cookie: str = "", headers: Dict = None):
        self.cookie = cookie
        self.headers = headers or {}
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                **self.headers,
            }
        )
        if cookie:
            self.client.headers["Cookie"] = cookie

    @abstractmethod
    async def search(self, city: str, keyword: str = "", page: int = 1) -> List[RawHouse]:
        """
        搜索房源
        Args:
            city: 城市名称
            keyword: 搜索关键词
            page: 页码
        Returns:
            原始房源列表
        """
        pass

    async def fetch_detail(self, source_url: str) -> Optional[RawHouse]:
        """
        获取房源详情（可选实现）

        默认返回 None，表示该平台不提供/暂未实现详情抓取。
        需要的平台可覆写此方法；不覆写也不会导致类无法实例化。
        Args:
            source_url: 房源链接
        Returns:
            补充后的房源信息，或 None
        """
        return None

    async def check_health(self) -> Dict:
        """
        检查爬虫健康状态
        Returns:
            {"status": "ok"|"error", "message": "..."}
        """
        return {"status": "ok", "message": "未实现健康检查"}

    @staticmethod
    def normalize(raw: RawHouse) -> Dict:
        """
        将原始房源标准化为数据库模型字段

        纯函数，不依赖实例，因此管理器可以直接用爬虫类调用，
        无需为标准化创建（并泄漏）HTTP 客户端。
        """
        return {
            "source": raw.source,
            "source_id": raw.source_id,
            "source_url": raw.source_url,
            "title": raw.title or "无标题",
            "description": raw.description,
            "city": raw.city,
            "district": raw.district,
            "area": raw.area,
            "community": raw.community,
            "address": raw.address,
            "longitude": raw.longitude,
            "latitude": raw.latitude,
            "price": raw.price,
            "rent_type": raw.rent_type,
            "room_type": raw.room_type,
            "area_size": raw.area_size,
            "orientation": raw.orientation,
            "publish_time": raw.publish_time,
            "publisher": raw.publisher,
            "publisher_id": raw.publisher_id,
            "images": json.dumps(raw.images, ensure_ascii=False) if raw.images else "[]",
            "tags": "|".join(raw.tags) if raw.tags else None,
            "raw_data": json.dumps(raw.raw_data, ensure_ascii=False) if raw.raw_data else None,
        }

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        return False
