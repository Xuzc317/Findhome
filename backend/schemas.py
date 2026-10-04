from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== 基础模型 ====================

class HouseBase(BaseModel):
    """房源基础信息"""
    title: str
    price: Optional[int] = None
    city: Optional[str] = None
    district: Optional[str] = None
    source: str
    source_url: str
    rent_type: int = 0
    publish_time: Optional[datetime] = None


class HouseCreate(HouseBase):
    """创建房源"""
    source_id: Optional[str] = None
    description: Optional[str] = None
    area: Optional[str] = None
    community: Optional[str] = None
    address: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    room_type: Optional[str] = None
    area_size: Optional[float] = None
    orientation: Optional[str] = None
    publisher: Optional[str] = None
    publisher_id: Optional[str] = None
    images: Optional[str] = "[]"
    tags: Optional[str] = None
    raw_data: Optional[str] = None


class HouseUpdate(BaseModel):
    """更新房源"""
    price: Optional[int] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    agent_score: Optional[int] = None
    ad_score: Optional[int] = None
    suspicious_score: Optional[int] = None
    confidence_score: Optional[int] = None
    is_duplicate: Optional[bool] = None
    duplicate_of: Optional[str] = None
    commute_duration: Optional[int] = None
    commute_distance: Optional[float] = None


class HouseResponse(HouseBase):
    """房源响应模型"""
    id: str
    create_time: datetime
    update_time: datetime
    description: Optional[str] = None
    area: Optional[str] = None
    community: Optional[str] = None
    address: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    room_type: Optional[str] = None
    area_size: Optional[float] = None
    orientation: Optional[str] = None
    crawl_time: datetime
    last_active_time: Optional[datetime] = None
    publisher: Optional[str] = None
    images: Optional[str] = "[]"
    tags: Optional[str] = None
    agent_score: int = 0
    ad_score: int = 0
    suspicious_score: int = 0
    confidence_score: int = 50
    is_duplicate: bool = False
    commute_duration: Optional[int] = None
    commute_distance: Optional[float] = None

    class Config:
        from_attributes = True


# ==================== 搜索/筛选请求 ====================

class HouseSearchParams(BaseModel):
    """房源搜索参数"""
    city: Optional[str] = None
    district: Optional[str] = None
    source: Optional[str] = None
    keyword: Optional[str] = None
    keyword_exclude: Optional[str] = None
    from_price: Optional[int] = None
    to_price: Optional[int] = None
    rent_type: Optional[int] = None  # -1表示全部
    # 可多选：如 "3" 只整租；"3,4" 整租+公寓
    rent_types: Optional[str] = None
    # 房型档位多选：studio,1b1l,2b1l,3b1l,4b+
    layouts: Optional[str] = None
    interval_day: Optional[int] = None  # 最近N天
    page: int = 0
    page_size: int = 20
    sort_by: str = "publish_time"  # publish_time/price/walk/distance/risk/score
    sort_order: str = "desc"  # asc/desc
    # 地铁站
    station_id: Optional[str] = None
    station: Optional[str] = None        # 站名（与 station_id 二选一）
    walk_max_m: Optional[int] = None     # 步行距离上限（米）
    # 通勤筛选
    commute_max_duration: Optional[int] = None
    # 风险筛选（均为可解释规则分值）
    max_agent_score: Optional[int] = None
    max_ad_score: Optional[int] = None
    max_suspicious_score: Optional[int] = None
    min_confidence_score: Optional[int] = None
    hide_duplicates: bool = True
    # 只返回有坐标的房源（地图/地铁筛选场景）
    only_with_coord: bool = False


class HouseSearchResponse(BaseModel):
    """搜索响应"""
    total: int
    page: int
    page_size: int
    houses: List[HouseResponse]


# ==================== 数据源相关 ====================

class SourceStatus(BaseModel):
    """数据源状态"""
    source: str
    display_name: str
    enabled: bool
    status: str  # pending/ready/error/needs_login
    last_crawl_time: Optional[datetime] = None
    houses_count: int = 0
    error_message: Optional[str] = None
    needs_login: bool = False


class CrawlRequest(BaseModel):
    """手动触发爬虫请求"""
    source: str
    city: Optional[str] = None
    keyword: Optional[str] = None
    pages: int = 1
    rent_type: int = 0          # 仅贝壳: 0全部 1合租 3整租
    with_detail: int = 0        # 为前 N 条抓取详情


class CrawlResponse(BaseModel):
    """爬虫响应"""
    source: str
    status: str
    message: str
    houses_count: int = 0


# ==================== 地图相关 ====================

class MapHouseQuery(BaseModel):
    """地图房源查询"""
    city: str
    source: Optional[str] = None
    keyword: Optional[str] = None
    rent_type: Optional[int] = None
    interval_day: Optional[int] = 30
    max_price: Optional[int] = None


class MapHouseItem(BaseModel):
    """地图房源项"""
    id: str
    longitude: float
    latitude: float
    price: Optional[int] = None
    source: str
    source_url: str
    title: str
    icon: Optional[str] = None


# ==================== 通勤相关 ====================

class CommuteConfig(BaseModel):
    """通勤配置"""
    destination: str
    longitude: float
    latitude: float
    max_duration: Optional[int] = 60  # 分钟


class CommuteResult(BaseModel):
    """通勤结果"""
    house_id: str
    duration: int  # 分钟
    distance: float  # 公里
    route_type: str  # transit/driving/walking


# ==================== 地铁 / 定位 ====================

class MetroSyncRequest(BaseModel):
    """同步高德地铁站点坐标"""
    city: Optional[str] = "深圳"
    lines: Optional[List[str]] = None   # 只同步指定线路；不传=全部
    overwrite: bool = False             # 是否覆盖已有坐标


class MetroDistanceRequest(BaseModel):
    """计算房源到地铁站的步行距离"""
    limit: int = 200          # 本次最多处理多少条房源
    only_missing: bool = True  # 只算还没算过的
    max_calls: int = 400       # 本次最多调用多少次高德（配额保护）


class GeoLocateRequest(BaseModel):
    """批量推断房源位置"""
    city: Optional[str] = "深圳"
    limit: int = 10            # 本次处理条数（建议小批量，多次调用即可增量推进）
    only_missing: bool = True
    use_llm: bool = True       # 规则解析置信度低时是否调用大模型
    max_calls: int = 60        # 高德调用上限


class LayoutBackfillRequest(BaseModel):
    """回填房型解析结果"""
    city: Optional[str] = None
    only_missing: bool = True
    limit: int = 5000


class GeoReportRequest(BaseModel):
    """回写一条定位结果（来源可以是后端高德、也可以是浏览器 JS API）"""
    house_id: str
    lng: float
    lat: float
    source: str = "amap_js"       # platform/amap_poi/amap_geocode/amap_js/llm_text/llm_image/manual
    precision: Optional[str] = None
    confidence: Optional[int] = None
    query: Optional[str] = None
    note: Optional[str] = None


class StationUpsertRequest(BaseModel):
    """新增/更新站点（含坐标）"""
    city: str = "深圳"
    name: str
    lng: Optional[float] = None
    lat: Optional[float] = None
    lines: Optional[List[str]] = None   # 所属线路名，如 ["1号线","2号线"]
    source: str = "amap_js"


class StationDistanceReport(BaseModel):
    """回写一条步行距离结果"""
    house_id: str
    station_id: str
    walk_meters: Optional[int] = None
    walk_minutes: Optional[int] = None
    straight_meters: Optional[int] = None
    status: str = "ok"                  # ok/no_route/error
    message: Optional[str] = None
    provider: str = "amap"


# ==================== 需求匹配 ====================

class ProfileSaveRequest(BaseModel):
    """保存"我的通勤选址条件" """
    name: str
    city: str = "深圳"
    stations: List[str] = []
    max_straight_m: int = 1000
    max_walk_minutes: int = 20
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    layouts: List[str] = []          # studio / 1b1l / 2b1l / 3b1l / 4b+
    require_elevator: bool = False
    min_newness_score: Optional[int] = None
    avoid_old_small: bool = True
    notes: str = ""
