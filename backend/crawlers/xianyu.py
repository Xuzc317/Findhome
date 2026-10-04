"""
闲鱼租房爬虫
需要登录Cookie，使用网页版搜索
"""

import re
import json
from typing import List, Optional
from datetime import datetime
from urllib.parse import quote
from backend.crawlers.base import BaseCrawler, RawHouse


class XianyuCrawler(BaseCrawler):
    """闲鱼爬虫"""

    SOURCE_NAME = "xianyu"
    DISPLAY_NAME = "闲鱼"
    NEEDS_LOGIN = True

    def __init__(self, cookie: str = ""):
        super().__init__(cookie=cookie)
        self.base_url = "https://s.2.taobao.com"

    async def search(self, city: str, keyword: str = "", page: int = 1) -> List[RawHouse]:
        """搜索闲鱼房源"""
        if not self.cookie:
            print("⚠️ 闲鱼: 未提供Cookie，需要登录")
            return []

        search_keyword = f"{city} 租房"
        if keyword:
            search_keyword = f"{city} {keyword}"

        url = "https://s.2.taobao.com/list/"
        params = {
            "q": search_keyword,
            "spm": "2007.1000337.5.1",
            "page": page,
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return self._parse_list(response.text, city)
        except Exception as e:
            print(f"❌ 闲鱼搜索失败: {e}")
            return []

    def _parse_list(self, html: str, city: str) -> List[RawHouse]:
        """解析闲鱼列表"""
        # 闲鱼页面结构经常变化，这里做基础解析
        # 实际使用时可能需要根据当前页面结构调整
        houses = []

        # 尝试从页面中提取商品数据
        # 闲鱼通常使用动态加载，这里提供基础框架

        # 如果有登录Cookie，可以尝试直接调用API
        # 否则提示需要登录

        print("⚠️ 闲鱼: 当前实现为基础框架，需要登录后抓取")
        return houses

    async def check_health(self) -> dict:
        """检查健康状态"""
        try:
            response = await self.client.get("https://s.2.taobao.com", timeout=10)
            if response.status_code == 200:
                return {"status": "ok", "message": "闲鱼可访问"}
            return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
