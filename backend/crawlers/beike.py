"""
贝壳找房爬虫
需要登录Cookie，使用网页版搜索
"""

import re
import json
from typing import List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from backend.crawlers.base import BaseCrawler, RawHouse


class BeikeCrawler(BaseCrawler):
    """贝壳找房爬虫"""

    SOURCE_NAME = "beike"
    DISPLAY_NAME = "贝壳找房"
    NEEDS_LOGIN = True

    # 城市编码映射
    CITY_CODES = {
        "北京": "bj",
        "上海": "sh",
        "深圳": "sz",
        "广州": "gz",
        "杭州": "hz",
        "成都": "cd",
        "南京": "nj",
        "武汉": "wh",
        "西安": "xa",
        "重庆": "cq",
    }

    def __init__(self, cookie: str = ""):
        super().__init__(cookie=cookie)
        self.base_url = "https://{city}.zu.ke.com"

    async def search(self, city: str, keyword: str = "", page: int = 1) -> List[RawHouse]:
        """搜索贝壳房源"""
        city_code = self.CITY_CODES.get(city, "")
        if not city_code:
            print(f"⚠️ 贝壳: 未支持城市 {city}")
            return []

        if not self.cookie:
            print("⚠️ 贝壳: 未提供Cookie，需要登录")
            return []

        url = f"https://{city_code}.zu.ke.com/zufang"
        params = {"pn": page}
        if keyword:
            # 贝壳的关键词搜索通过URL路径实现
            url = f"https://{city_code}.zu.ke.com/zufang/rs{keyword}"

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return self._parse_list(response.text, city)
        except Exception as e:
            print(f"❌ 贝壳搜索失败: {e}")
            return []

    def _parse_list(self, html: str, city: str) -> List[RawHouse]:
        """解析房源列表页"""
        soup = BeautifulSoup(html, "html.parser")
        houses = []

        # 贝壳PC版列表选择器
        for item in soup.select("div.content__list--item"):
            try:
                # 标题和链接
                title_link = item.select_one("a.twoline")
                if not title_link:
                    continue

                title = title_link.get_text(strip=True)
                href = title_link.get("href", "")
                if href.startswith("/"):
                    href = f"https://{self.CITY_CODES.get(city, 'bj')}.zu.ke.com{href}"

                # 价格
                price_elem = item.select_one("span.content__list--item-price em")
                price = None
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = self._extract_price(price_text)

                # 描述信息
                desc_elem = item.select_one("p.content__list--item--des")
                desc = desc_elem.get_text(strip=True) if desc_elem else ""

                # 提取区域和地址
                district = ""
                area = ""
                if desc_elem:
                    des_spans = desc_elem.find_all("a")
                    if len(des_spans) >= 1:
                        district = des_spans[0].get_text(strip=True)
                    if len(des_spans) >= 2:
                        area = des_spans[1].get_text(strip=True)

                # 出租类型
                rent_type = self._detect_rent_type(title, desc)

                # 图片
                img_elem = item.select_one("img")
                images = []
                if img_elem:
                    img_src = img_elem.get("data-src") or img_elem.get("src", "")
                    if img_src:
                        images.append(img_src)

                # 标签
                tags = []
                for tag in item.select("i.content__item__tag"):
                    tags.append(tag.get_text(strip=True))

                house = RawHouse(
                    source=self.SOURCE_NAME,
                    source_url=href,
                    title=title,
                    city=city,
                    district=district,
                    area=area,
                    price=price,
                    rent_type=rent_type,
                    description=desc,
                    images=images,
                    tags=tags,
                    publish_time=datetime.now(),  # 贝壳列表页通常不显示发布时间
                )
                houses.append(house)

            except Exception as e:
                print(f"⚠️ 解析房源失败: {e}")
                continue

        return houses

    async def fetch_detail(self, source_url: str) -> Optional[RawHouse]:
        """获取房源详情"""
        try:
            response = await self.client.get(source_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # 详细描述
            desc = ""
            desc_elem = soup.select_one("div.introduction")
            if desc_elem:
                desc = desc_elem.get_text(separator="\n", strip=True)

            # 更多图片
            images = []
            for img in soup.select("img#topImg"):
                src = img.get("src", "")
                if src:
                    images.append(src)

            # 位置
            longitude = None
            latitude = None
            # 尝试从页面JS中提取坐标
            script_tags = soup.find_all("script")
            for script in script_tags:
                text = script.string or ""
                if "longitude" in text and "latitude" in text:
                    lng_match = re.search(r'longitude["\']?\s*[:=]\s*["\']?([\d.]+)', text)
                    lat_match = re.search(r'latitude["\']?\s*[:=]\s*["\']?([\d.]+)', text)
                    if lng_match and lat_match:
                        longitude = float(lng_match.group(1))
                        latitude = float(lat_match.group(1))
                        break

            return RawHouse(
                source=self.SOURCE_NAME,
                source_url=source_url,
                description=desc,
                images=images,
                longitude=longitude,
                latitude=latitude,
            )

        except Exception as e:
            print(f"❌ 获取详情失败: {e}")
            return None

    def _extract_price(self, text: str) -> Optional[int]:
        """提取价格"""
        match = re.search(r'(\d+)', text.replace(",", ""))
        if match:
            price = int(match.group(1))
            if 300 <= price <= 100000:
                return price
        return None

    def _detect_rent_type(self, title: str, desc: str) -> int:
        """检测出租类型"""
        text = f"{title} {desc}".lower()
        if "整租" in text:
            return 3
        if "合租" in text:
            return 1
        if "公寓" in text:
            return 4
        return 0

    async def check_health(self) -> dict:
        """检查健康状态"""
        try:
            response = await self.client.get("https://bj.zu.ke.com", timeout=10)
            if response.status_code == 200:
                return {"status": "ok", "message": "贝壳网页可访问"}
            return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
