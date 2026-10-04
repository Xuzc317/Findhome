from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from backend.models import House
from backend.schemas import HouseSearchParams
from typing import List, Tuple
from datetime import datetime, timedelta


class HouseSearchService:
    """房源搜索服务"""

    # 前端排序字段别名 -> 数据库字段
    SORT_FIELDS = {
        "publish_time": House.publish_time,
        "price": House.price,
        "distance": House.commute_duration,
        "commute": House.commute_duration,
        "risk": House.suspicious_score,
        "agent": House.agent_score,
        "score": House.confidence_score,
        "confidence": House.confidence_score,
        "crawl_time": House.crawl_time,
        "create_time": House.create_time,
    }

    def __init__(self, db: Session):
        self.db = db

    def search(self, params: HouseSearchParams) -> Tuple[List[House], int]:
        """搜索房源，返回 (房源列表, 总数)"""
        query = self.db.query(House)

        # 基础筛选
        if params.city:
            query = query.filter(House.city == params.city)

        if params.district and params.district != "全部":
            query = query.filter(House.district == params.district)

        if params.source and params.source != "all":
            query = query.filter(House.source == params.source)

        # 价格筛选
        if params.from_price is not None:
            query = query.filter(House.price >= params.from_price)
        if params.to_price is not None:
            query = query.filter(House.price <= params.to_price)

        # 租房类型
        if params.rent_type is not None and params.rent_type != -1:
            query = query.filter(House.rent_type == params.rent_type)

        # 发布时间筛选
        if params.interval_day and params.interval_day > 0:
            since = datetime.now() - timedelta(days=params.interval_day)
            query = query.filter(House.publish_time >= since)

        # 关键词包含筛选
        if params.keyword:
            keywords = [k.strip() for k in params.keyword.split() if k.strip()]
            if keywords:
                conditions = []
                for kw in keywords:
                    conditions.append(
                        or_(
                            House.title.contains(kw),
                            House.description.contains(kw),
                            House.tags.contains(kw),
                            House.address.contains(kw),
                            House.community.contains(kw),
                        )
                    )
                query = query.filter(and_(*conditions))

        # 关键词排除筛选
        if params.keyword_exclude:
            excludes = [k.strip() for k in params.keyword_exclude.split() if k.strip()]
            if excludes:
                for ex in excludes:
                    query = query.filter(
                        ~or_(
                            House.title.contains(ex),
                            House.description.contains(ex),
                            House.tags.contains(ex),
                        )
                    )

        # 通勤时间筛选
        if params.commute_max_duration is not None:
            query = query.filter(
                or_(
                    House.commute_duration <= params.commute_max_duration,
                    House.commute_duration.is_(None),
                )
            )

        # 风险评分筛选
        if params.max_agent_score is not None:
            query = query.filter(House.agent_score <= params.max_agent_score)

        # 隐藏重复房源
        if params.hide_duplicates:
            query = query.filter(House.is_duplicate == False)

        # 统计总数
        total = query.count()

        # 排序（NULL 值统一排在最后，避免“价格未知”的房源占据价格排序首位）
        sort_field = self.SORT_FIELDS.get(params.sort_by, House.publish_time)
        null_rank = sort_field.is_(None)
        if params.sort_order == "desc":
            query = query.order_by(null_rank, desc(sort_field), desc(House.create_time))
        else:
            query = query.order_by(null_rank, asc(sort_field), desc(House.create_time))

        # 分页
        offset = params.page * params.page_size
        houses = query.offset(offset).limit(params.page_size).all()

        return houses, total

    def get_by_id(self, house_id: str) -> House:
        """根据ID获取房源"""
        return self.db.query(House).filter(House.id == house_id).first()

    def get_map_houses(self, city: str, source: str = None,
                       keyword: str = None, rent_type: int = None,
                       interval_day: int = 30, max_price: int = None) -> List[House]:
        """获取地图展示用房源（简化查询）"""
        query = self.db.query(House).filter(House.city == city)

        if source and source != "all":
            query = query.filter(House.source == source)

        if keyword:
            query = query.filter(
                or_(
                    House.title.contains(keyword),
                    House.description.contains(keyword),
                )
            )

        if rent_type is not None and rent_type != -1:
            query = query.filter(House.rent_type == rent_type)

        if interval_day and interval_day > 0:
            since = datetime.now() - timedelta(days=interval_day)
            query = query.filter(House.publish_time >= since)

        if max_price:
            query = query.filter(House.price <= max_price)

        # 地图最多返回2000条
        query = query.filter(House.is_duplicate == False)
        return query.order_by(desc(House.publish_time)).limit(2000).all()

    def get_sources_count(self, city: str = None) -> dict:
        """获取各数据源房源数量统计"""
        query = self.db.query(House.source, func.count(House.id))
        if city:
            query = query.filter(House.city == city)
        query = query.group_by(House.source)
        return {row[0]: row[1] for row in query.all()}
