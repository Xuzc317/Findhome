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
    interval_day: Optional[int] = None  # 最近N天
    page: int = 0
    page_size: int = 20
    sort_by: str = "publish_time"  # publish_time/price/distance/risk/score
    sort_order: str = "desc"  # asc/desc
    # 通勤筛选
    commute_max_duration: Optional[int] = None
    # 风险筛选
    max_agent_score: Optional[int] = None
    hide_duplicates: bool = True


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
