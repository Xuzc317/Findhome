from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Float,
    Boolean, create_engine, Index, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4()).replace("-", "")


class House(Base):
    """统一房源数据模型"""
    __tablename__ = "houses"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 来源信息
    source = Column(String(50), nullable=False, index=True, comment="数据来源")
    source_id = Column(String(255), nullable=True, comment="来源平台原始ID")
    source_url = Column(String(1024), nullable=False, comment="原始链接")

    # 基础信息
    title = Column(String(512), nullable=False, comment="标题")
    description = Column(Text, nullable=True, comment="描述/正文")

    # 地理位置
    city = Column(String(64), nullable=True, index=True, comment="城市")
    district = Column(String(64), nullable=True, index=True, comment="行政区")
    area = Column(String(128), nullable=True, comment="商圈/区域")
    community = Column(String(128), nullable=True, comment="小区")
    address = Column(String(512), nullable=True, comment="详细地址")
    longitude = Column(Float, nullable=True, comment="经度")
    latitude = Column(Float, nullable=True, comment="纬度")

    # 价格与房型
    price = Column(Integer, nullable=True, comment="月租金")
    rent_type = Column(Integer, default=0, comment="出租类型: 0未知 1合租 2单间 3整租 4公寓")
    room_type = Column(String(64), nullable=True, comment="房型描述(平台原文)")
    area_size = Column(Float, nullable=True, comment="面积")
    orientation = Column(String(32), nullable=True, comment="朝向")

    # 房型结构化（由标题/正文解析，解析不出则留空，不猜测）
    bedrooms = Column(Integer, nullable=True, comment="卧室数(0=单间/开间)")
    living_rooms = Column(Integer, nullable=True, comment="客厅数")
    layout_key = Column(String(16), nullable=True, index=True,
                        comment="房型档位: studio/1b1l/2b1l/3b1l/4b+/unknown")
    layout_confidence = Column(Integer, nullable=True, comment="房型解析置信度 0-100")
    layout_evidence = Column(String(255), nullable=True, comment="房型判定依据原文片段")

    # 时间
    publish_time = Column(DateTime, nullable=True, comment="发布时间(平台未展示则为空)")
    last_active_time = Column(DateTime, nullable=True, comment="平台展示的最近维护/活跃时间")
    crawl_time = Column(DateTime, default=datetime.now, comment="采集时间")

    # 发布者
    publisher = Column(String(255), nullable=True, comment="发布者名称")
    publisher_id = Column(String(255), nullable=True, comment="发布者ID")

    # 媒体
    images = Column(Text, default="[]", comment="图片URL列表(JSON)")
    tags = Column(String(512), nullable=True, comment="标签")

    # 原始数据（保留用于调试和后续处理）
    raw_data = Column(Text, nullable=True, comment="原始数据JSON")

    # 风险评分（0-100）
    agent_score = Column(Integer, default=0, comment="中介概率评分")
    ad_score = Column(Integer, default=0, comment="广告概率评分")
    suspicious_score = Column(Integer, default=0, comment="异常概率评分")
    confidence_score = Column(Integer, default=50, comment="可信度评分")

    # 状态
    status = Column(Integer, default=0, comment="状态: 0正常 1已删除 2已分析")

    # 去重标记
    is_duplicate = Column(Boolean, default=False, comment="是否重复房源")
    duplicate_of = Column(String(32), nullable=True, comment="指向主房源ID")

    # 通勤信息（可选）
    commute_duration = Column(Integer, nullable=True, comment="通勤时间(分钟)")
    commute_distance = Column(Float, nullable=True, comment="通勤距离(公里)")

    # 地理定位溯源：坐标可能是平台给的，也可能是我们根据文字/图片推断的，
    # 必须记录来源与精度，界面上要能区分，绝不把推断值当成平台事实。
    geo_source = Column(String(24), nullable=True,
                        comment="坐标来源: platform/amap_poi/amap_geocode/llm_text/llm_image/manual")
    geo_precision = Column(String(24), nullable=True,
                           comment="精度: building/community/street/district/station/unknown")
    geo_confidence = Column(Integer, nullable=True, comment="定位置信度 0-100")
    geo_query = Column(String(255), nullable=True, comment="实际用于地理编码的文本")
    geo_note = Column(String(255), nullable=True, comment="定位说明/命中依据")
    geo_updated_at = Column(DateTime, nullable=True, comment="定位更新时间")

    # 索引优化
    __table_args__ = (
        Index('idx_city_source', 'city', 'source'),
        Index('idx_price', 'price'),
        Index('idx_pub_time', 'publish_time'),
        Index('idx_source_url', 'source_url'),
        Index('idx_layout', 'city', 'layout_key'),
    )


class CrawlLog(Base):
    """爬虫执行日志"""
    __tablename__ = "crawl_logs"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    source = Column(String(50), nullable=False, comment="数据源")
    city = Column(String(64), nullable=True, comment="城市")
    status = Column(String(20), default="running", comment="状态: running/success/failed")
    message = Column(Text, nullable=True, comment="日志信息")
    houses_count = Column(Integer, default=0, comment="采集房源数")
    start_time = Column(DateTime, default=datetime.now)
    end_time = Column(DateTime, nullable=True)


class SourceConfig(Base):
    """数据源配置"""
    __tablename__ = "source_configs"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    source = Column(String(50), nullable=False, unique=True, comment="数据源名称")
    enabled = Column(Boolean, default=False, comment="是否启用")
    city = Column(String(64), nullable=True, comment="目标城市")
    extra_config = Column(Text, nullable=True, comment="额外配置JSON")
    last_crawl_time = Column(DateTime, nullable=True, comment="上次采集时间")
    status = Column(String(20), default="pending", comment="状态: pending/ready/error")
    error_message = Column(Text, nullable=True, comment="错误信息")


# ==================== 地铁数据 ====================

class MetroLine(Base):
    """地铁线路"""
    __tablename__ = "metro_lines"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    city = Column(String(64), nullable=False, index=True, comment="城市")
    name = Column(String(64), nullable=False, comment="线路名，如 1号线")
    alias = Column(String(64), nullable=True, comment="别名，如 罗宝线")
    color = Column(String(16), nullable=True, comment="线路色")
    status = Column(String(20), default="operating", comment="operating/building")
    sort_order = Column(Integer, default=0, comment="展示排序")
    source = Column(String(24), nullable=True, comment="数据来源: static/amap")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('idx_metro_line_city_name', 'city', 'name', unique=True),
    )


class MetroStation(Base):
    """地铁站点（站点为主体，换乘站只存一条，通过关联表挂多条线路）"""
    __tablename__ = "metro_stations"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    city = Column(String(64), nullable=False, index=True, comment="城市")
    name = Column(String(64), nullable=False, comment="站点名，如 深大")
    lng = Column(Float, nullable=True, comment="经度（无来源则留空）")
    lat = Column(Float, nullable=True, comment="纬度（无来源则留空）")
    coord_source = Column(String(24), nullable=True, comment="坐标来源: static/amap")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('idx_metro_station_city_name', 'city', 'name', unique=True),
    )


class MetroLineStation(Base):
    """线路-站点关联（含站序）"""
    __tablename__ = "metro_line_stations"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    line_id = Column(String(32), nullable=False, index=True)
    station_id = Column(String(32), nullable=False, index=True)
    seq = Column(Integer, default=0, comment="线路内站序，从1开始")

    __table_args__ = (
        Index('idx_line_station', 'line_id', 'station_id', unique=True),
    )


class StationDistance(Base):
    """房源到地铁站的距离（缓存真实步行路径结果，可重复计算）

    只存高德返回的真实步行数据；没有坐标或未计算时不写行，
    界面上显示为“未计算”，不估算。
    """
    __tablename__ = "station_distances"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    house_id = Column(String(32), nullable=False, index=True)
    station_id = Column(String(32), nullable=False, index=True)
    walk_meters = Column(Integer, nullable=True, comment="步行路径距离(米)")
    walk_minutes = Column(Integer, nullable=True, comment="步行耗时(分钟)")
    straight_meters = Column(Integer, nullable=True, comment="直线距离(米)，仅作参考")
    provider = Column(String(24), default="amap", comment="数据来源")
    status = Column(String(20), default="ok", comment="ok/no_route/error")
    message = Column(String(255), nullable=True, comment="失败原因")
    computed_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('idx_house_station', 'house_id', 'station_id', unique=True),
        Index('idx_station_walk', 'station_id', 'walk_meters'),
    )
