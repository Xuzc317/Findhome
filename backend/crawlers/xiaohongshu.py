"""
小红书租房爬虫
需要登录Cookie，使用网页版搜索
"""

import re
import json
from typing import List, Optional
from datetime import datetime
from backend.crawlers.base import BaseCrawler, RawHouse, extract_price


class XiaohongshuCrawler(BaseCrawler):
    """小红书爬虫"""

    SOURCE_NAME = "xiaohongshu"
    DISPLAY_NAME = "小红书"
    NEEDS_LOGIN = True

    def __init__(self, cookie: str = ""):
        super().__init__(cookie=cookie)
        self.base_url = "https://www.xiaohongshu.com"
        self.api_url = "https://www.xiaohongshu.com/api/sns/web/v1/search/notes"

    async def search(self, city: str, keyword: str = "", page: int = 1) -> List[RawHouse]:
        """搜索小红书笔记"""
        if not self.cookie:
            print("⚠️ 小红书: 未提供Cookie，需要登录")
            return []

        search_keyword = f"{city} 租房"
        if keyword:
            search_keyword = f"{city} {keyword}"

        # 小红书搜索API
        params = {
            "keyword": search_keyword,
            "page": page,
            "page_size": 20,
            "search_id": "",
            "sort": "general",
            "note_type": "0",
        }

        try:
            response = await self.client.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()
            return self._parse_results(data, city)
        except Exception as e:
            print(f"❌ 小红书搜索失败: {e}")
            return []

    def _parse_results(self, data: dict, city: str) -> List[RawHouse]:
        """解析搜索结果"""
        houses = []

        if not data or "data" not in data:
            return houses

        notes = data["data"].get("items", [])

        for note in notes:
            try:
                note_card = note.get("note_card", {})
                title = note_card.get("title", "")
                desc = note_card.get("desc", "")
                note_id = note_card.get("note_id", "")
                user = note_card.get("user", {})
                publisher = user.get("nickname", "")

                # 构建笔记链接
                source_url = f"https://www.xiaohongshu.com/explore/{note_id}"

                # 提取价格
                price = self._extract_price(f"{title} {desc}")

                # 提取图片
                images = []
                image_list = note_card.get("image_list", [])
                for img in image_list:
                    url = img.get("url_default", "")
                    if url:
                        images.append(url)

                # 发布时间
                pub_time = None
                time_str = note_card.get("time", "")
                if time_str:
                    try:
                        pub_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                    except:
                        pass

                # 出租类型
                rent_type = self._detect_rent_type(f"{title} {desc}")

                house = RawHouse(
                    source=self.SOURCE_NAME,
                    source_id=note_id,
                    source_url=source_url,
                    title=title or "小红书租房笔记",
                    description=desc,
                    city=city,
                    price=price,
                    rent_type=rent_type,
                    publisher=publisher,
                    images=images,
                    publish_time=pub_time or datetime.now(),
                    tags=[city, "小红书"],
                )
                houses.append(house)

            except Exception as e:
                print(f"⚠️ 解析笔记失败: {e}")
                continue

        return houses

    def _extract_price(self, text: str) -> Optional[int]:
        """从标题/正文提取价格（保守策略，避免把手机号识别成租金）"""
        return extract_price(text)

    def _detect_rent_type(self, text: str) -> int:
        """检测出租类型"""
        text = text.lower()
        if any(kw in text for kw in ["整租", "整套", "一居室"]):
            return 3
        if any(kw in text for kw in ["合租", "主卧", "次卧", "单间", "室友"]):
            return 1
        if "公寓" in text:
            return 4
        return 0

    async def check_health(self) -> dict:
        """检查健康状态"""
        try:
            response = await self.client.get("https://www.xiaohongshu.com", timeout=10)
            if response.status_code == 200:
                return {"status": "ok", "message": "小红书可访问"}
            return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
