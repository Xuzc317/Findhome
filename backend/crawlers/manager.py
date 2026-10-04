"""
爬虫管理器
统一管理各数据源的采集任务
"""

from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime
from backend.models import House, CrawlLog, SourceConfig
from backend.services.risk import RiskScorer
from backend.services.dedup import DedupService
from backend.config import get_settings

# 导入各爬虫
from backend.crawlers.douban import DoubanCrawler
from backend.crawlers.beike import BeikeCrawler
from backend.crawlers.xianyu import XianyuCrawler
from backend.crawlers.xiaohongshu import XiaohongshuCrawler


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

    def get_crawler(self, source: str):
        """获取爬虫实例"""
        crawler_class = self.CRAWLERS.get(source)
        if not crawler_class:
            return None

        # 获取对应Cookie
        cookie = getattr(self.settings, f"{source}_cookie", "")
        return crawler_class(cookie=cookie)

    async def crawl(self, source: str, city: str, keyword: str = "", pages: int = 1) -> Dict:
        """
        执行爬虫任务
        返回: {"success": bool, "count": int, "message": str}
        """
        crawler = self.get_crawler(source)
        if not crawler:
            return {"success": False, "count": 0, "message": f"未知数据源: {source}"}

        # 记录日志
        log = CrawlLog(
            source=source,
            city=city,
            status="running",
            message=f"开始采集: {city} {keyword}",
        )
        self.db.add(log)
        self.db.commit()

        all_houses = []
        try:
            for page in range(1, pages + 1):
                houses = await crawler.search(city=city, keyword=keyword, page=page)
                if not houses:
                    break
                all_houses.extend(houses)

            # 关闭爬虫
            await crawler.close()

            # 处理结果
            inserted_count = await self._process_houses(all_houses, source)

            # 更新日志
            log.status = "success"
            log.houses_count = inserted_count
            log.end_time = datetime.now()
            log.message = f"成功采集 {inserted_count} 条房源"
            self.db.commit()

            return {
                "success": True,
                "count": inserted_count,
                "message": f"成功采集 {inserted_count} 条房源",
            }

        except Exception as e:
            log.status = "failed"
            log.end_time = datetime.now()
            log.message = f"采集失败: {str(e)}"
            self.db.commit()

            await crawler.close()
            return {"success": False, "count": 0, "message": str(e)}

    async def _process_houses(self, raw_houses, source: str) -> int:
        """处理采集到的房源数据：标准化、去重、评分、入库"""
        if not raw_houses:
            return 0

        crawler_class = self.CRAWLERS.get(source)
        if crawler_class is None:
            return 0

        # 标准化（normalize 是静态纯函数，不需要创建爬虫实例/HTTP 客户端）
        unique_houses = []
        seen_urls = set()
        for raw in raw_houses:
            data = crawler_class.normalize(raw)
            url = data.get("source_url")
            if url and url in seen_urls:
                continue  # 同一批次内按链接去重
            if url:
                seen_urls.add(url)
            unique_houses.append(House(**data))

        dedup = DedupService(self.db)
        inserted = 0

        for house in unique_houses:
            # 1) 已采集过的链接：更新可变字段，不重复入库
            existing = None
            if house.source_url:
                existing = self.db.query(House).filter(
                    House.source_url == house.source_url
                ).first()

            if existing:
                # 已采集过：刷新可变字段，保留首次采集时间与风险/去重标记
                existing.title = house.title
                existing.price = house.price
                existing.description = house.description
                existing.images = house.images
                existing.tags = house.tags
                existing.source_id = house.source_id or existing.source_id
                existing.publisher = house.publisher or existing.publisher
                existing.publisher_id = house.publisher_id or existing.publisher_id
                existing.publish_time = house.publish_time or existing.publish_time
                existing.district = house.district or existing.district
                existing.area = house.area or existing.area
                existing.community = house.community or existing.community
                existing.address = house.address or existing.address
                existing.longitude = house.longitude or existing.longitude
                existing.latitude = house.latitude or existing.latitude
                existing.update_time = datetime.now()
                continue

            # 2) 跨平台/同小区重复检测
            matched = dedup.find_duplicate(house)
            if matched is not None:
                house.is_duplicate = True
                house.duplicate_of = matched.id

            # 3) 风险评分
            scores = RiskScorer.score_house(house)
            house.agent_score = scores["agent"]
            house.ad_score = scores["ad"]
            house.suspicious_score = scores["suspicious"]

            # 可信度 = 100 - 综合风险
            house.confidence_score = max(0, 100 - max(
                house.agent_score, house.ad_score, house.suspicious_score
            ))

            self.db.add(house)
            inserted += 1

        self.db.commit()
        return inserted

    async def check_all_health(self) -> List[Dict]:
        """检查所有数据源健康状态"""
        results = []
        for source, crawler_class in self.CRAWLERS.items():
            try:
                cookie = getattr(self.settings, f"{source}_cookie", "")
                crawler = crawler_class(cookie=cookie)
                health = await crawler.check_health()
                await crawler.close()

                results.append({
                    "source": source,
                    "display_name": crawler_class.DISPLAY_NAME,
                    "needs_login": crawler_class.NEEDS_LOGIN,
                    **health,
                })
            except Exception as e:
                results.append({
                    "source": source,
                    "display_name": crawler_class.DISPLAY_NAME,
                    "status": "error",
                    "message": str(e),
                })

        return results
