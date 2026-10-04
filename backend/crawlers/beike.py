"""
贝壳找房（租房）爬虫

实测结论（2026-10-04）：
- 列表页 https://{city}.zu.ke.com/zufang 无需登录即可访问，可解析约 30 条/页。
- 详情页 https://{city}.zu.ke.com/zufang/{house_code}.html 返回验证码/登录中间页，
  按项目边界（不绕过验证码与访问控制）不尝试抓取详情；
  详情页可在用户本人浏览器中正常打开，因此 source_url 仍然有效。
- 列表页只展示“X天前维护”，不展示独立发布时间：
  该值写入 last_active_time，publish_time 留空（不猜测）。
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from backend.crawlers.base import (
    STATUS_BLOCKED,
    STATUS_EMPTY,
    STATUS_ERROR,
    STATUS_NEEDS_LOGIN,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    BaseCrawler,
    RawHouse,
    detect_block,
    parse_relative_time,
)

DES_PATTERN = re.compile(r"^([^/]+)/([\d.]+)㎡/([^/]*)/([^/]*)/([^/]*)")
# 兜底：主正则未命中时，从描述文本中单独取面积/户型（仍然只读平台自己的文案）
AREA_FALLBACK = re.compile(r"([\d.]+)\s*㎡")
ROOM_FALLBACK = re.compile(r"(\d+室\d+厅(?:\d+卫)?)")


class BeikeCrawler(BaseCrawler):
    """贝壳找房爬虫（列表页无需登录）"""

    SOURCE_NAME = "beike"
    DISPLAY_NAME = "贝壳找房"
    NEEDS_LOGIN = False  # 列表页公开可访问；配 Cookie 只是提高稳定性
    MIN_REQUEST_INTERVAL = 8.0  # 贝壳风控敏感，实测连续快速请求会触发验证码

    CITY_CODES = {
        "北京": "bj", "上海": "sh", "深圳": "sz", "广州": "gz",
        "杭州": "hz", "成都": "cd", "南京": "nj", "武汉": "wh",
        "西安": "xa", "重庆": "cq", "苏州": "su", "天津": "tj",
        "长沙": "cs",
    }
    SUPPORTED_CITIES = CITY_CODES

    # 出租类型 -> 列表路径（0 为默认全部路径）
    RENT_TYPE_PATHS = {
        0: "/zufang/",
        3: "/zufang/rt200600000001/",  # 整租
        1: "/zufang/rt200600000002/",  # 合租
    }

    DETAIL_AVAILABLE = False
    DETAIL_UNAVAILABLE_REASON = (
        "贝壳详情页返回验证码/登录中间页（实测 HTTP 200 但为 CAPTCHA 页），"
        "按项目边界不绕过验证码，因此不抓取详情；source_url 可在浏览器正常打开。"
    )

    def __init__(self, cookie: str = "", rent_type: int = 0):
        super().__init__(cookie=cookie)
        self.rent_type = rent_type

    # ---------- 采集 ----------

    async def search(self, city: str, keyword: str = "", page: int = 1) -> List[RawHouse]:
        """搜索贝壳房源（列表页）"""
        city_code = self.CITY_CODES.get(city)
        if not city_code:
            self.set_status(STATUS_UNAVAILABLE,
                            f"未支持城市 {city}，可用: {', '.join(self.CITY_CODES)}")
            return []

        path = self.RENT_TYPE_PATHS.get(self.rent_type, "/zufang/")
        if keyword:
            # 贝壳关键词搜索形如 /zufang/rs关键词/
            path = f"/zufang/rs{keyword}/"
        if page > 1:
            # 分页形如 /zufang/pg2/ 或 /zufang/rt.../pg2/
            path = path.rstrip("/") + f"/pg{page}/"

        url = f"https://{city_code}.zu.ke.com{path}"

        try:
            response = await self.get(url)
        except Exception as e:
            self.set_status(STATUS_ERROR, f"{type(e).__name__}: {e}")
            return []

        if response.status_code != 200:
            self.set_status(STATUS_ERROR, f"HTTP {response.status_code}")
            return []

        houses, reason = self._parse_list(response.text, city)
        if reason:
            return []

        if not houses:
            self.set_status(STATUS_EMPTY, f"{city} 未解析到房源（可能该条件下无结果）")
            return []

        self.set_status(STATUS_OK, f"解析到 {len(houses)} 条")
        return houses

    def _parse_list(self, html: str, city: str) -> Tuple[List[RawHouse], Optional[str]]:
        """解析房源列表页。返回 (房源列表, 失败原因或None)"""
        soup = BeautifulSoup(html, "html.parser")

        items = soup.select("div.content__list--item")
        if not items:
            # 区分验证码 / 登录 / 结构变化
            reason = detect_block(html)
            if reason:
                self.set_status(STATUS_BLOCKED, reason)
                return [], reason
            page_title = soup.title.get_text(strip=True) if soup.title else ""
            if "登录" in page_title:
                msg = f"贝壳返回登录页（title={page_title}），配置 BEIKE_COOKIE 后重试"
                self.set_status(STATUS_NEEDS_LOGIN, msg)
                return [], msg
            msg = "页面无 content__list--item，可能是结构变化或被限流"
            self.set_status(STATUS_UNAVAILABLE, msg)
            return [], msg

        houses: List[RawHouse] = []
        for item in items:
            try:
                house = self._parse_item(item, city)
                if house:
                    houses.append(house)
            except Exception:
                continue  # 单条解析失败不影响整页

        return houses, None

    def _parse_item(self, item, city: str) -> Optional[RawHouse]:
        """解析单个房源卡片"""
        title_link = item.select_one("a.twoline")
        if not title_link:
            return None

        title = title_link.get_text(strip=True)
        href = title_link.get("href", "")
        if not title or not href:
            return None
        if href.startswith("/"):
            city_code = self.CITY_CODES.get(city, "bj")
            href = f"https://{city_code}.zu.ke.com{href}"

        # 房源编号：贝壳卡片上的 data-house_code
        source_id = item.get("data-house_code") or None
        if not source_id:
            m = re.search(r"/([A-Z]{2}\d+)\.html", href)
            source_id = m.group(1) if m else None

        # 价格
        price = None
        price_el = item.select_one("span.content__list--item-price em")
        if price_el:
            m = re.search(r"(\d+)", price_el.get_text(strip=True).replace(",", ""))
            if m:
                price = int(m.group(1))

        # 描述行：区-商圈-小区/面积/朝向/户型/楼层
        district = area = community = None
        area_size = None
        orientation = None
        room_type = None
        floor_text = None
        desc_el = item.select_one("p.content__list--item--des")
        desc_text = ""
        if desc_el:
            # get_text(" ") 会在嵌套标签之间插入空格，形成 "南山区 - 南头 - 小区 / 89.00㎡ / 南"，
            # 必须先归一化 "/" 两侧的空白，否则面积/户型/朝向都匹配不到
            desc_text = re.sub(r"\s+", " ", desc_el.get_text(" ", strip=True)).strip()
            normalized = re.sub(r"\s*/\s*", "/", desc_text)
            m = DES_PATTERN.match(normalized)
            if m:
                region, size, orient, room, floor = m.groups()
                parts = [p.strip() for p in region.split("-") if p.strip()]
                if len(parts) >= 1:
                    district = parts[0]
                if len(parts) >= 2:
                    area = parts[1]
                if len(parts) >= 3:
                    community = parts[2]
                try:
                    area_size = float(size)
                except ValueError:
                    area_size = None
                orientation = re.sub(r"\s+", " ", orient).strip() or None
                room_type = room.strip() or None
                floor_text = floor.strip() or None

            # 兜底：主正则未命中（页面布局变体）时，按字段单独提取
            if area_size is None:
                m_area = AREA_FALLBACK.search(desc_text)
                if m_area:
                    try:
                        area_size = float(m_area.group(1))
                    except ValueError:
                        area_size = None
            if room_type is None:
                m_room = ROOM_FALLBACK.search(desc_text)
                if m_room:
                    room_type = m_room.group(1)

        # 兜底：描述未命中时，从区域链接取行政区和商圈
        if not district:
            links = desc_el.select("a") if desc_el else []
            if len(links) >= 1:
                district = links[0].get_text(strip=True) or None
            if len(links) >= 2:
                area = links[1].get_text(strip=True) or None
        if not community:
            # 标题形如 "整租·农光南路 3室1厅 南/北"
            m = re.match(r"^[^·]*·\s*([^\s]+)", title)
            if m:
                community = m.group(1)
        if room_type is None:
            # 户型也可能只出现在标题里（如 "整租·麒麟花园B区 3室1厅 南"）
            m_room = ROOM_FALLBACK.search(title)
            if m_room:
                room_type = m_room.group(1)

        # 标签（真实标签，如 近地铁/精装/押一付一/新上）
        tags = [t.get_text(strip=True) for t in item.select("i[class*='content__item__tag']")]
        tags = [t for t in tags if t]

        # 最近维护时间（注意：不是发布时间）
        last_active = None
        time_el = item.select_one("span.content__list--item--time")
        time_text = time_el.get_text(strip=True) if time_el else ""
        if time_text:
            last_active = parse_relative_time(time_text)

        # 出租类型：标题前缀优先，其次请求路径
        rent_type = self.rent_type
        if title.startswith("整租"):
            rent_type = 3
        elif title.startswith("合租"):
            rent_type = 1
        elif "公寓" in title:
            rent_type = 4

        images: List[str] = []
        img = item.select_one("img")
        if img:
            src = img.get("data-src") or img.get("src") or ""
            if src and "default/250-182" not in src:  # 跳过占位图
                images.append(src)

        return RawHouse(
            source=self.SOURCE_NAME,
            source_id=source_id,
            source_url=href,
            title=title,
            description=desc_text or None,
            city=city,
            district=district,
            area=area,
            community=community,
            price=price,
            rent_type=rent_type,
            room_type=room_type,
            area_size=area_size,
            orientation=orientation,
            publish_time=None,  # 列表页不展示发布时间，留空
            last_active_time=last_active,
            images=images,
            tags=tags + [city],
            raw_data={
                "house_code": source_id,
                "time_text": time_text,
                "time_semantics": "最近维护时间(非发布时间)",
                "floor": floor_text,
            },
        )

    # ---------- 详情 ----------

    async def fetch_detail(self, source_url: str) -> Optional[RawHouse]:
        """详情页被验证码保护，按边界不抓取，直接返回 None"""
        return None

    # ---------- 健康检查 ----------

    async def check_health(self) -> dict:
        """真实探针：抓取北京列表页并确认能解析出房源卡片"""
        url = "https://bj.zu.ke.com/zufang/"
        try:
            response = await self.get(url)
        except Exception as e:
            self.set_status(STATUS_ERROR, f"{type(e).__name__}: {e}")
            return {"status": STATUS_ERROR, "message": str(e), "verified": False}

        if response.status_code != 200:
            msg = f"HTTP {response.status_code}"
            self.set_status(STATUS_ERROR, msg)
            return {"status": STATUS_ERROR, "message": msg, "verified": False}

        houses, reason = self._parse_list(response.text, "北京")
        if reason:
            return {"status": self.last_status, "message": reason, "verified": False}

        msg = f"列表页可解析 {len(houses)} 条房源；详情页受验证码保护（不抓取）"
        self.set_status(STATUS_OK, msg)
        return {"status": STATUS_OK, "message": msg, "verified": True}
