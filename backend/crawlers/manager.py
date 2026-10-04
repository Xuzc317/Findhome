"""
爬虫管理器
统一管理各数据源的采集任务

设计要点：
- 健康检查是“真实请求 + 真实解析”的探针，而不是只看 HTTP 200。
- 平台要求登录 / 触发验证码 / 接口下线时，如实上报对应状态，绝不把
  “被拦截导致的 0 条”当成“该城市没有房源”。
- 写库操作带事务回滚，可重复运行（同一链接不会重复插入）。
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.crawlers.base import (
    STATUS_BLOCKED,
    STATUS_EMPTY,
    STATUS_ERROR,
    STATUS_NEEDS_LOGIN,
    STATUS_OK,
    STATUS_UNAVAILABLE,
)
from backend.crawlers.beike import BeikeCrawler
from backend.crawlers.douban import DoubanCrawler
from backend.crawlers.xianyu import XianyuCrawler
from backend.crawlers.xiaohongshu import XiaohongshuCrawler
from backend.models import CrawlLog, House
from backend.services.dedup import DedupService
from backend.services.risk import RiskScorer

# 需要落库到 CrawlLog.status 的取值（success 之外的均为“未成功”）
LOG_STATUS = {
    STATUS_OK: "success",
    STATUS_EMPTY: "empty",
    STATUS_NEEDS_LOGIN: "needs_login",
    STATUS_BLOCKED: "blocked",
    STATUS_UNAVAILABLE: "unavailable",
    STATUS_ERROR: "error",
}


class CrawlerManager:
    """爬虫管理器"""

    CRAWLERS = {
        "douban": DoubanCrawler,
        "beike": BeikeCrawler,
        "xianyu": XianyuCrawler,
        "xiaohongshu": XiaohongshuCrawler,
    }

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    # ---------- 实例构建 ----------

    def get_crawler(self, source: str, **kwargs):
        """获取爬虫实例（自动注入该平台 Cookie）"""
        crawler_class = self.CRAWLERS.get(source)
        if not crawler_class:
            return None

        cookie = getattr(self.settings, f"{source}_cookie", "") or ""
        return crawler_class(cookie=cookie, **kwargs)

    # ---------- 采集主流程 ----------

    async def crawl(
        self,
        source: str,
        city: str,
        keyword: str = "",
        pages: int = 1,
        rent_type: int = 0,
        with_detail: int = 0,
    ) -> Dict:
        """
        执行爬虫任务

        Returns:
            {"success": bool, "status": str, "count": int, "updated": int, "message": str}
        """
        crawler_class = self.CRAWLERS.get(source)
        if crawler_class is None:
            return {"success": False, "status": STATUS_UNAVAILABLE,
                    "count": 0, "updated": 0, "message": f"未知数据源: {source}"}

        crawler_kwargs = {}
        if source == "beike":
            crawler_kwargs["rent_type"] = rent_type
        crawler = self.get_crawler(source, **crawler_kwargs)

        log = CrawlLog(
            source=source,
            city=city,
            status="running",
            message=f"开始采集: {city} {keyword}".strip(),
        )
        self.db.add(log)
        self.db.commit()

        all_houses = []
        try:
            for page in range(1, pages + 1):
                houses = await crawler.search(city=city, keyword=keyword, page=page)
                if not houses:
                    # 无数据：可能是最后一页，也可能是被拦截/需登录，状态已在 crawler 上
                    break
                all_houses.extend(houses)

            # 可选：抓取前 N 条的详情，补全正文/图片
            if with_detail > 0 and all_houses:
                await self._enrich_details(crawler, all_houses[:with_detail])

            inserted, updated = self._process_houses(all_houses, source)

            status = crawler.last_status
            message = crawler.last_message or f"采集 {len(all_houses)} 条"
            if all_houses:
                # 已经拿到数据就算成功；后续页被拦截时在消息里如实说明
                if status != STATUS_OK:
                    message = f"{message}（后续页未完成，已保存已获取部分）"
                status = STATUS_OK

            log.status = LOG_STATUS.get(status, "success")
            log.houses_count = inserted
            log.end_time = datetime.now()
            log.message = f"{message}；新增 {inserted} 条，更新 {updated} 条"
            self.db.commit()

            return {
                "success": bool(all_houses),
                "status": status,
                "count": inserted,
                "updated": updated,
                "total": len(all_houses),
                "message": log.message,
            }

        except Exception as e:
            self.db.rollback()
            log.status = "error"
            log.end_time = datetime.now()
            log.message = f"采集失败: {type(e).__name__}: {e}"
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
            return {"success": False, "status": STATUS_ERROR, "count": 0, "updated": 0,
                    "message": log.message}
        finally:
            try:
                await crawler.close()
            except Exception:
                pass

    async def _enrich_details(self, crawler, houses) -> None:
        """用详情页补全正文/图片（仅在 Adapter 声明详情可用时执行）"""
        if not getattr(crawler, "DETAIL_AVAILABLE", True):
            return
        enriched = 0
        for house in houses:
            if not house.source_url:
                continue
            try:
                detail = await crawler.fetch_detail(house.source_url)
            except Exception:
                detail = None
            if not detail:
                continue
            # 只补空缺字段，不覆盖列表页已有的真实值
            house.description = house.description or detail.description
            house.images = house.images or detail.images
            house.publisher = house.publisher or detail.publisher
            house.publish_time = house.publish_time or detail.publish_time
            house.longitude = house.longitude or detail.longitude
            house.latitude = house.latitude or detail.latitude
            enriched += 1

    # ---------- 入库 ----------

    def _process_houses(self, raw_houses, source: str):
        """标准化、去重、评分、入库。返回 (新增数, 更新数)"""
        if not raw_houses:
            return 0, 0

        crawler_class = self.CRAWLERS.get(source)
        if crawler_class is None:
            return 0, 0

        # 标准化（normalize 是静态纯函数，无需创建实例/HTTP 客户端）
        normalized: List[House] = []
        seen_urls = set()
        for raw in raw_houses:
            data = crawler_class.normalize(raw)
            url = data.get("source_url")
            if url and url in seen_urls:
                continue  # 同一批次内按链接去重
            if url:
                seen_urls.add(url)
            normalized.append(House(**data))

        dedup = DedupService(self.db)
        inserted = 0
        updated = 0

        for house in normalized:
            existing = None
            if house.source_url:
                existing = self.db.query(House).filter(
                    House.source_url == house.source_url
                ).first()

            if existing:
                # 已采集过：刷新可变字段，保留首次采集时间与风险/去重标记
                existing.title = house.title
                existing.price = house.price if house.price is not None else existing.price
                existing.description = house.description or existing.description
                existing.images = house.images if house.images and house.images != "[]" else existing.images
                existing.tags = house.tags or existing.tags
                existing.source_id = house.source_id or existing.source_id
                existing.publisher = house.publisher or existing.publisher
                existing.publisher_id = house.publisher_id or existing.publisher_id
                existing.publish_time = house.publish_time or existing.publish_time
                existing.last_active_time = house.last_active_time or existing.last_active_time
                existing.district = house.district or existing.district
                existing.area = house.area or existing.area
                existing.community = house.community or existing.community
                existing.address = house.address or existing.address
                existing.longitude = house.longitude or existing.longitude
                existing.latitude = house.latitude or existing.latitude
                existing.rent_type = house.rent_type or existing.rent_type
                existing.room_type = house.room_type or existing.room_type
                existing.area_size = house.area_size or existing.area_size
                existing.orientation = house.orientation or existing.orientation
                if house.raw_data:
                    existing.raw_data = house.raw_data
                existing.update_time = datetime.now()
                updated += 1
                continue

            # 跨平台/同小区重复检测
            matched = dedup.find_duplicate(house)
            if matched is not None:
                house.is_duplicate = True
                house.duplicate_of = matched.id

            # 风险评分（仅基于可解释规则）
            scores = RiskScorer.score_house(house)
            house.agent_score = scores["agent"]
            house.ad_score = scores["ad"]
            house.suspicious_score = scores["suspicious"]
            house.confidence_score = max(0, 100 - max(
                house.agent_score, house.ad_score, house.suspicious_score
            ))

            self.db.add(house)
            inserted += 1

        self.db.commit()
        return inserted, updated

    # ---------- 健康检查 ----------

    async def check_all_health(self) -> List[Dict]:
        """逐个数据源做真实探针"""
        results = []
        for source, crawler_class in self.CRAWLERS.items():
            crawler = None
            try:
                crawler = self.get_crawler(source)
                health = await crawler.check_health()
                results.append({
                    "source": source,
                    "display_name": crawler_class.DISPLAY_NAME,
                    "needs_login": crawler_class.NEEDS_LOGIN,
                    "cookie_configured": crawler.has_cookie,
                    "detail_available": getattr(crawler_class, "DETAIL_AVAILABLE", True),
                    "detail_unavailable_reason": getattr(
                        crawler_class, "DETAIL_UNAVAILABLE_REASON", ""),
                    "supported_cities": list(getattr(crawler_class, "SUPPORTED_CITIES", {})),
                    "status": health.get("status", STATUS_ERROR),
                    "message": health.get("message", ""),
                    "verified": health.get("verified", False),
                })
            except Exception as e:
                results.append({
                    "source": source,
                    "display_name": crawler_class.DISPLAY_NAME,
                    "needs_login": crawler_class.NEEDS_LOGIN,
                    "cookie_configured": False,
                    "status": STATUS_ERROR,
                    "message": f"{type(e).__name__}: {e}",
                    "verified": False,
                })
            finally:
                if crawler is not None:
                    try:
                        await crawler.close()
                    except Exception:
                        pass

        return results
