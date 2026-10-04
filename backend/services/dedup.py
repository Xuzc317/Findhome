from sqlalchemy.orm import Session
from backend.models import House
from typing import List, Tuple
import hashlib
import json


class DedupService:
    """房源去重服务"""

    def __init__(self, db: Session):
        self.db = db

    def find_duplicates(self, houses: List[House]) -> List[Tuple[House, House]]:
        """
        在给定房源列表中找出重复对
        返回: [(新房源, 已有房源), ...]
        """
        duplicates = []

        for house in houses:
            dup = self.find_duplicate(house)
            if dup:
                duplicates.append((house, dup))

        return duplicates

    def find_duplicate(self, house: House) -> House:
        """检查单个房源是否与库中已有房源重复（返回命中的已有房源，无则返回 None）"""
        # 1. 链接完全匹配
        if house.source_url:
            existing = self.db.query(House).filter(
                House.source_url == house.source_url
            ).first()
            if existing:
                return existing

        # 2. 标题+价格+城市匹配
        if house.title and house.price and house.city:
            existing = self.db.query(House).filter(
                House.title == house.title,
                House.price == house.price,
                House.city == house.city,
                House.source != house.source,  # 跨平台重复更有意义
            ).first()
            if existing:
                return existing

        # 3. 同小区+同价格+相似标题
        if house.community and house.price:
            candidates = self.db.query(House).filter(
                House.community == house.community,
                House.price == house.price,
            ).limit(10).all()

            for candidate in candidates:
                if self._title_similarity(house.title, candidate.title) > 0.7:
                    return candidate

        return None

    def _title_similarity(self, a: str, b: str) -> float:
        """简单标题相似度（Jaccard）"""
        if not a or not b:
            return 0.0
        set_a = set(a.lower())
        set_b = set(b.lower())
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def mark_duplicates(self, duplicates: List[Tuple[House, House]]) -> int:
        """标记重复房源，返回标记数量"""
        count = 0
        for new_house, existing in duplicates:
            new_house.is_duplicate = True
            new_house.duplicate_of = existing.id
            count += 1
        return count

    def calculate_image_hash(self, image_urls: List[str]) -> str:
        """计算图片URL列表的哈希（用于图片去重）"""
        if not image_urls:
            return ""
        urls_str = "|".join(sorted(image_urls))
        return hashlib.md5(urls_str.encode()).hexdigest()[:16]
