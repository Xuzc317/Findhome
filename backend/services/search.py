from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from backend.models import House, StationDistance
from backend.schemas import HouseSearchParams
from typing import List, Optional, Tuple
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

    # 参与关键词匹配的文本列
    TEXT_COLUMNS = (
        House.title,
        House.description,
        House.tags,
        House.address,
        House.community,
        House.publisher,
    )

    @classmethod
    def _text_match(cls, term: str):
        """构造“任一文本列包含 term”的条件。

        必须对可空列做 COALESCE：SQL 三值逻辑下 `NULL LIKE '%x%'` 结果是 NULL，
        取反后仍是 NULL，会导致“任意一个排除词清空全部结果”。
        """
        return or_(*[
            func.coalesce(column, "").contains(term, autoescape=True)
            for column in cls.TEXT_COLUMNS
        ])

    def search(self, params: HouseSearchParams,
               with_station_id: Optional[str] = None) -> Tuple[List[House], int]:
        """搜索房源，返回 (房源列表, 总数)

        Args:
            with_station_id: 指定后，返回的房源会带上到该站的步行距离（已缓存的）
        """
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

        # 出租类型：优先多选，其次单选
        rent_types = self._parse_int_list(params.rent_types)
        if rent_types:
            query = query.filter(House.rent_type.in_(rent_types))
        elif params.rent_type is not None and params.rent_type != -1:
            query = query.filter(House.rent_type == params.rent_type)

        # 房型档位
        layouts = self._parse_str_list(params.layouts)
        if layouts:
            query = query.filter(House.layout_key.in_(layouts))

        # 有坐标（地图/地铁筛选场景）
        if params.only_with_coord:
            query = query.filter(House.longitude.isnot(None),
                                 House.latitude.isnot(None))

        # 地铁站步行距离（只认真实步行结果，no_route 不参与）
        if params.station_id:
            query = query.join(
                StationDistance,
                and_(StationDistance.house_id == House.id,
                     StationDistance.station_id == params.station_id,
                     StationDistance.status == "ok"),
            )
            if params.walk_max_m:
                query = query.filter(StationDistance.walk_meters <= params.walk_max_m)

        # 发布时间筛选
        # 有效时间 = 发布时间，缺失时回退到平台展示的“最近维护时间”；
        # 两者都没有的房源不参与时间筛选（不猜测时间）
        if params.interval_day and params.interval_day > 0:
            since = datetime.now() - timedelta(days=params.interval_day)
            effective_time = func.coalesce(House.publish_time, House.last_active_time)
            query = query.filter(effective_time.isnot(None), effective_time >= since)

        # 关键词包含筛选
        if params.keyword:
            keywords = [k.strip() for k in params.keyword.split() if k.strip()]
            if keywords:
                conditions = [self._text_match(kw) for kw in keywords]
                query = query.filter(and_(*conditions))

        # 关键词排除筛选
        if params.keyword_exclude:
            excludes = [k.strip() for k in params.keyword_exclude.split() if k.strip()]
            if excludes:
                for ex in excludes:
                    query = query.filter(~self._text_match(ex))

        # 通勤时间筛选
        if params.commute_max_duration is not None:
            query = query.filter(
                or_(
                    House.commute_duration <= params.commute_max_duration,
                    House.commute_duration.is_(None),
                )
            )

        # 风险评分筛选（全部基于可解释规则计算出的分值）
        if params.max_agent_score is not None:
            query = query.filter(House.agent_score <= params.max_agent_score)
        if params.max_suspicious_score is not None:
            query = query.filter(House.suspicious_score <= params.max_suspicious_score)
        if params.max_ad_score is not None:
            query = query.filter(House.ad_score <= params.max_ad_score)
        if params.min_confidence_score is not None:
            query = query.filter(House.confidence_score >= params.min_confidence_score)

        # 隐藏重复房源
        if params.hide_duplicates:
            query = query.filter(House.is_duplicate == False)

        # 统计总数
        total = query.count()

        # 排序（NULL 值统一排在最后，避免“价格未知”的房源占据价格排序首位）
        # 走地铁筛选时，distance/walk 排序按真实步行距离
        if params.sort_by in ("distance", "walk", "station") and params.station_id:
            sort_field = StationDistance.walk_meters
        else:
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
            query = query.filter(self._text_match(keyword.strip()))

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

    # ---------- 工具 ----------

    @staticmethod
    def _parse_int_list(value: Optional[str]) -> List[int]:
        if not value:
            return []
        result = []
        for token in str(value).replace("，", ",").split(","):
            token = token.strip()
            if token.lstrip("-").isdigit():
                result.append(int(token))
        return result

    @staticmethod
    def _parse_str_list(value: Optional[str]) -> List[str]:
        if not value:
            return []
        return [t.strip() for t in str(value).replace("，", ",").split(",") if t.strip()]

    def station_distances(self, house_ids: List[str],
                          station_id: str) -> dict:
        """批量取房源到指定站点的步行距离（只返回已算好的）"""
        if not house_ids or not station_id:
            return {}
        rows = self.db.query(StationDistance).filter(
            StationDistance.house_id.in_(house_ids),
            StationDistance.station_id == station_id,
        ).all()
        return {row.house_id: row for row in rows}
