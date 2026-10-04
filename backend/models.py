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
    room_type = Column(String(64), nullable=True, comment="房型描述")
    area_size = Column(Float, nullable=True, comment="面积")
    orientation = Column(String(32), nullable=True, comment="朝向")

    # 时间
    publish_time = Column(DateTime, nullable=True, comment="发布时间")
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

    # 索引优化
    __table_args__ = (
        Index('idx_city_source', 'city', 'source'),
        Index('idx_price', 'price'),
        Index('idx_pub_time', 'publish_time'),
        Index('idx_source_url', 'source_url'),
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
