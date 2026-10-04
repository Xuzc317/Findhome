"""
豆瓣租房小组爬虫
基于公开网页抓取，无需登录
"""

import re
import json
from typing import List, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from backend.crawlers.base import BaseCrawler, RawHouse, extract_price


class DoubanCrawler(BaseCrawler):
    """豆瓣租房小组爬虫"""

    SOURCE_NAME = "douban"
    DISPLAY_NAME = "豆瓣租房"
    NEEDS_LOGIN = False

    # 豆瓣租房小组列表（可按需扩展）
    GROUPS = {
        "北京": ["26926", "279962"],      # 北京租房、北京租房豆瓣
        "上海": ["shanghaizufang", "383866"],  # 上海租房、上海租房小组
        "深圳": ["106955", "szsh"],       # 深圳租房、深圳租房团
        "广州": ["gzsh"],                 # 广州租房
        "杭州": ["hzsh"],                 # 杭州租房
        "成都": ["cdzufang"],             # 成都租房
    }

    def __init__(self, cookie: str = ""):
        super().__init__(cookie=cookie)
        self.base_url = "https://www.douban.com/group"

    async def search(self, city: str, keyword: str = "", page: int = 1) -> List[RawHouse]:
        """搜索豆瓣租房小组帖子"""
        houses = []
        group_ids = self.GROUPS.get(city, [])

        if not group_ids:
            print(f"⚠️ 豆瓣: 未配置城市 {city} 的小组")
            return houses

        for group_id in group_ids:
            try:
                group_houses = await self._fetch_group(group_id, city, keyword, page)
                houses.extend(group_houses)
            except Exception as e:
                print(f"❌ 豆瓣小组 {group_id} 抓取失败: {e}")

        return houses

    async def _fetch_group(self, group_id: str, city: str, keyword: str, page: int) -> List[RawHouse]:
        """抓取单个小组的帖子列表

        豆瓣小组讨论列表的真实表结构（4 列）:
            td.title  标题   |   td(无class) 作者   |   td.r-count 回应数   |   td.time 最后回应时间
        """
        url = f"{self.base_url}/{group_id}/discussion"
        params = {"start": (page - 1) * 25}
        if keyword:
            params["keyword"] = keyword

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        houses = []

        for tr in soup.select("table.olt tr"):
            title_td = tr.find("td", class_="title")
            if not title_td:
                continue

            title_link = title_td.find("a")
            if not title_link:
                continue

            title = (title_link.get("title") or title_link.get_text(strip=True) or "").strip()
            href = title_link.get("href", "")
            if not title or not href:
                continue

            # 跳过置顶和公告
            if any(kw in title for kw in ["置顶", "公告", "规则", "组规"]):
                continue

            tds = tr.find_all("td")

            # 作者（第 2 列）
            publisher = tds[1].get_text(strip=True) if len(tds) > 2 else ""

            # 发布时间：优先取 td.time，否则取最后一列
            time_td = tr.find("td", class_="time") or (tds[-1] if tds else None)
            pub_time = self._parse_time(time_td.get_text(strip=True)) if time_td else None

            # 提取价格
            price = self._extract_price(title)

            # 判断出租类型
            rent_type = self._detect_rent_type(title)

            # 帖子 ID
            id_match = re.search(r"/topic/(\d+)", href)

            house = RawHouse(
                source=self.SOURCE_NAME,
                source_id=id_match.group(1) if id_match else None,
                source_url=href,
                title=title,
                city=city,
                price=price,
                rent_type=rent_type,
                publish_time=pub_time,
                publisher=publisher,
                tags=[city, "豆瓣小组"],
            )
            houses.append(house)

        return houses

    async def fetch_detail(self, source_url: str) -> Optional[RawHouse]:
        """获取帖子详情"""
        try:
            response = await self.client.get(source_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # 获取正文
            topic_content = soup.select_one(".topic-content")
            if topic_content:
                # 移除script和style
                for script in topic_content(["script", "style"]):
                    script.decompose()
                description = topic_content.get_text(separator="\n", strip=True)
            else:
                description = ""

            # 获取图片
            images = []
            for img in soup.select(".topic-content img"):
                src = img.get("src", "")
                if src:
                    images.append(src)

            # 获取发布者
            publisher = ""
            user_card = soup.select_one(".user-card")
            if user_card:
                publisher = user_card.get_text(strip=True)

            return RawHouse(
                source=self.SOURCE_NAME,
                source_url=source_url,
                description=description,
                images=images,
                publisher=publisher,
            )

        except Exception as e:
            print(f"❌ 获取详情失败 {source_url}: {e}")
            return None

    def _extract_price(self, text: str) -> Optional[int]:
        """从标题提取价格（保守策略，避免把手机号识别成租金）"""
        return extract_price(text)

    def _detect_rent_type(self, text: str) -> int:
        """从标题判断出租类型"""
        text = text.lower()
        if any(kw in text for kw in ["整租", "整套", "一居室", "一室一厅", "两室一厅"]):
            return 3  # 整租
        if any(kw in text for kw in ["合租", "主卧", "次卧", "单间", "找室友", "招室友"]):
            return 1  # 合租
        if any(kw in text for kw in ["公寓", "loft"]):
            return 4  # 公寓
        return 0  # 未知

    def _parse_time(self, time_text: str) -> Optional[datetime]:
        """解析豆瓣时间文本

        豆瓣小组列表页实际格式：
            "10-04 05:59" / "10-04" / "05:59" / "今天 05:59" / "昨天 23:46"
            "2024-01-15" / "2024-01-15 10:23"
        """
        if not time_text:
            return None

        now = datetime.now()
        text = time_text.strip()

        def _with_year(month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
            """补全年份；若解析结果比当前时间还晚，说明是去年的帖子"""
            try:
                value = now.replace(month=month, day=day, hour=hour, minute=minute,
                                    second=0, microsecond=0)
            except ValueError:
                return now
            if value > now + timedelta(days=1):
                value = value.replace(year=value.year - 1)
            return value

        # "今天 10:23" / "昨天 10:23"
        for prefix, day_offset in (("今天", 0), ("昨天", 1)):
            if text.startswith(prefix):
                rest = text[len(prefix):].strip()
                try:
                    h, m = map(int, rest.split(":"))
                except ValueError:
                    return now
                value = now.replace(hour=h, minute=m, second=0, microsecond=0)
                return value - timedelta(days=day_offset)

        # "2024-01-15 10:23" 或 "2024-01-15"
        match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$", text)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            hour = int(match.group(4)) if match.group(4) else 0
            minute = int(match.group(5)) if match.group(5) else 0
            try:
                return datetime(year, month, day, hour, minute)
            except ValueError:
                return now

        # "10-04 05:59" 或 "10-04"（无年份）
        match = re.match(r"^(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$", text)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            hour = int(match.group(3)) if match.group(3) else 0
            minute = int(match.group(4)) if match.group(4) else 0
            return _with_year(month, day, hour, minute)

        # "05:59"（今天）
        match = re.match(r"^(\d{1,2}):(\d{2})$", text)
        if match:
            return now.replace(hour=int(match.group(1)), minute=int(match.group(2)),
                               second=0, microsecond=0)

        # 无法识别：返回 None，避免把采集时间误当成发布时间
        return None

    async def check_health(self) -> dict:
        """检查健康状态"""
        try:
            response = await self.client.get("https://www.douban.com", timeout=10)
            if response.status_code == 200:
                return {"status": "ok", "message": "豆瓣可访问"}
            return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
