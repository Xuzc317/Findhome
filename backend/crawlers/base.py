"""
数据源爬虫基类
所有平台爬虫都应继承此类并实现抽象方法
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import json
import re
import httpx

from backend.config import get_settings

# ==================== 采集状态 ====================
# 用于替代“HTTP 200 就算健康”的粗糙判断，如实反映平台真实响应
STATUS_OK = "ok"                    # 真实拿到并解析出数据
STATUS_EMPTY = "empty"              # 请求成功但该条件下无结果
STATUS_NEEDS_LOGIN = "needs_login"  # 平台要求登录（Cookie/扫码）
STATUS_BLOCKED = "blocked"          # 被验证码/风控拦截（不绕过）
STATUS_UNAVAILABLE = "unavailable"  # 接口已下线或结构不可解析
STATUS_ERROR = "error"              # 网络/解析异常

# 被拦截页面特征。
# 只保留高置信度的短语：像 "verify"/"captcha" 这类小写英文在正常页面的内联 JS 里
# 也常出现（例如贝壳的 captchaDomain），会造成误判。
BLOCK_PATTERNS = [
    "请点击下方按钮继续浏览",
    "点我继续浏览",
    "CAPTCHA",          # 贝壳验证码页的 <title>
    "访问过于频繁",
    "检测到异常",
    "安全验证",
    "请求过于频繁",
]

LOGIN_PATTERNS = [
    "扫码登录",
    "请先登录",
    "无登录信息",
    "登录后查看",
    "立即登录后",
]

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


_RELATIVE_TIME_PATTERN = re.compile(r"(\d+)\s*(秒|分钟|分|小时|天|周|个月|月)\s*前")


def parse_relative_time(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """解析"3天前""2小时前""刚刚""今天""昨天"这类相对时间。

    仅在文本确实包含相对时间表述时返回时间，否则返回 None（不猜测）。
    """
    if not text:
        return None
    now = now or datetime.now()

    if "刚刚" in text:
        return now
    if "今天" in text:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if "昨天" in text:
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

    match = _RELATIVE_TIME_PATTERN.search(text)
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "秒":
        delta = timedelta(seconds=amount)
    elif unit in ("分钟", "分"):
        delta = timedelta(minutes=amount)
    elif unit == "小时":
        delta = timedelta(hours=amount)
    elif unit == "天":
        delta = timedelta(days=amount)
    elif unit == "周":
        delta = timedelta(weeks=amount)
    else:  # 个月 / 月
        delta = timedelta(days=amount * 30)

    return now - delta


def detect_block(html: str) -> Optional[str]:
    """检测响应是否为拦截/登录中间页，返回原因；正常页面返回 None"""
    if not html:
        return None
    head = html[:6000]
    for pat in BLOCK_PATTERNS:
        if pat in head:
            return f"命中拦截特征: {pat}"
    for pat in LOGIN_PATTERNS:
        if pat in head:
            return f"命中登录特征: {pat}"
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
    # 平台展示的“最近维护/活跃时间”，与发布时间语义不同，单独存放
    last_active_time: Optional[datetime] = None
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
    # 支持的城市 -> 平台城市标识
    SUPPORTED_CITIES: Dict[str, str] = {}
    # 详情页是否可用（不可用时如实说明原因，不做无谓试探）
    DETAIL_AVAILABLE: bool = True
    DETAIL_UNAVAILABLE_REASON: str = ""

    def __init__(self, cookie: str = "", headers: Dict = None):
        self.cookie = cookie
        self.headers = headers or {}
        self.last_status: str = STATUS_OK
        self.last_message: str = ""
        self._last_request_at: Optional[datetime] = None
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "sec-ch-ua": '"Chromium";v="120", "Not(A:Brand";v="24", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                **self.headers,
            }
        )
        if cookie:
            self.client.headers["Cookie"] = cookie

    # ---------- 状态与限速 ----------

    def set_status(self, status: str, message: str = ""):
        self.last_status = status
        self.last_message = message

    @property
    def has_cookie(self) -> bool:
        return bool(self.cookie and self.cookie.strip())

    def request_interval(self) -> float:
        """请求间隔，避免触发平台风控"""
        try:
            base = float(get_settings().crawl_interval)
        except Exception:
            base = 2.0
        return max(base, self.MIN_REQUEST_INTERVAL)

    # 子类可提高最小间隔（平台越敏感数值越大）
    MIN_REQUEST_INTERVAL: float = 2.0

    async def polite_sleep(self):
        """两次请求之间的礼节性等待"""
        if self._last_request_at is not None:
            elapsed = (datetime.now() - self._last_request_at).total_seconds()
            wait = self.request_interval() - elapsed
            if wait > 0:
                await asyncio.sleep(wait)

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """带限速的 GET"""
        await self.polite_sleep()
        try:
            return await self.client.get(url, **kwargs)
        finally:
            self._last_request_at = datetime.now()

    # ---------- 子类实现 ----------

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

        默认返回 None，表示该平台不提供/暂不可用详情抓取。
        """
        return None

    async def check_health(self) -> Dict:
        """
        检查爬虫健康状态

        子类应覆写为“真实请求 + 真实解析”的探针，
        只判断 HTTP 200 无法发现验证码页/空壳 SPA。
        """
        return {"status": STATUS_OK, "message": "未实现健康检查"}

    # ---------- 标准化 ----------

    @staticmethod
    def normalize(raw: RawHouse) -> Dict:
        """
        将原始房源标准化为数据库模型字段

        纯函数，不依赖实例，因此管理器可以直接用爬虫类调用，
        无需为标准化创建（并泄漏）HTTP 客户端。

        缺失字段一律保持 None，不使用任何推测值填充。
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
            "last_active_time": raw.last_active_time,
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
