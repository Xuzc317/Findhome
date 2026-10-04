"""
豆瓣租房小组爬虫
基于公开网页抓取。未登录时可用，但豆瓣有频率风控：
一旦返回“请点击下方按钮继续浏览”的中间页，本 Adapter 会如实上报 blocked，
不会尝试绕过；此时可配置 DOUBAN_COOKIE（用户本人浏览器登录态）后重试。

列表页表结构（4 列）:
    td.title 标题 | td(无class) 作者 | td.r-count 回应数 | td.time 最后回应时间
注意：td.time 是“最后回应时间”，豆瓣小组列表页并不展示独立发布时间，
因此入库时写入 publish_time（作为该帖最近活跃时间），并同时记录原始文本。
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

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
    extract_price,
)


class DoubanCrawler(BaseCrawler):
    """豆瓣租房小组爬虫"""

    SOURCE_NAME = "douban"
    DISPLAY_NAME = "豆瓣租房"
    NEEDS_LOGIN = False
    MIN_REQUEST_INTERVAL = 5.0  # 豆瓣风控敏感，放慢请求

    # 城市 -> 小组 ID 列表
    # 标注 [已验证] 的为实际采集到过数据的 ID；其余需在未被风控时验证
    GROUPS: Dict[str, List[str]] = {
        "北京": ["26926", "279962"],        # [已验证] 2026-10-04 实采 59 条
        "上海": ["shanghaizufang"],         # [待验证]
        "深圳": ["106955"],                 # [待验证]
        "广州": ["gzsh"],                   # [待验证]
        "杭州": ["hzsh"],                   # [待验证]
        "成都": ["cdzufang"],               # [待验证]
    }
    SUPPORTED_CITIES = {city: ",".join(ids) for city, ids in GROUPS.items()}

    DETAIL_AVAILABLE = True  # 未被风控时可抓详情

    def __init__(self, cookie: str = "", groups: Optional[List[str]] = None):
        super().__init__(cookie=cookie)
        self.base_url = "https://www.douban.com/group"
        self.groups_override = groups or []
        self.raw_page_text: str = ""

    # ---------- 采集 ----------

    async def search(self, city: str, keyword: str = "", page: int = 1) -> List[RawHouse]:
        """搜索豆瓣租房小组帖子"""
        houses: List[RawHouse] = []
        group_ids = self.groups_override or self.GROUPS.get(city, [])

        if not group_ids:
            self.set_status(STATUS_UNAVAILABLE, f"未配置城市 {city} 的小组 ID，可用 --group 指定")
            return houses

        blocked_reason = None
        parsed_any = False

        for group_id in group_ids:
            try:
                group_houses, reason = await self._fetch_group(group_id, city, keyword, page)
            except Exception as e:  # 网络异常不应中断其他小组
                reason = f"请求异常: {type(e).__name__}: {e}"
                group_houses = []

            if reason:
                blocked_reason = reason
                # 被风控/需要登录时继续试下一个小组没有意义，直接停止
                if "拦截" in reason or "登录" in reason:
                    break
                continue

            parsed_any = True
            houses.extend(group_houses)

        if blocked_reason and not parsed_any:
            # 区分“被风控”与“需要登录”
            status = STATUS_NEEDS_LOGIN if "登录" in blocked_reason else STATUS_BLOCKED
            self.set_status(status, blocked_reason)
            return []

        if not houses:
            self.set_status(STATUS_EMPTY, f"{city} 未解析到帖子（可能小组 ID 失效或该页无内容）")
            return []

        self.set_status(STATUS_OK, f"解析到 {len(houses)} 条")
        return houses

    async def _fetch_group(self, group_id: str, city: str, keyword: str, page: int):
        """抓取单个小组的帖子列表。返回 (房源列表, 失败原因或None)"""
        url = f"{self.base_url}/{group_id}/discussion"
        params = {"start": (page - 1) * 25}
        if keyword:
            params["keyword"] = keyword

        response = await self.get(url, params=params)

        if response.status_code == 429:
            return [], "HTTP 429 请求过于频繁（豆瓣限流），拦截特征: 429"
        if response.status_code != 200:
            return [], f"HTTP {response.status_code}"

        self.raw_page_text = response.text

        reason = detect_block(response.text)
        if reason:
            return [], reason

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.select_one("table.olt")
        if table is None:
            # 200 但没有列表 → 可能是空小组、ID 失效或结构变化
            title = soup.select_one("h1")
            hint = title.get_text(strip=True)[:30] if title else "无 h1"
            return [], f"页面无 table.olt（{hint}）"

        houses: List[RawHouse] = []
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

            # 时间：优先 td.time，否则最后一列
            time_td = tr.find("td", class_="time") or (tds[-1] if tds else None)
            time_text = time_td.get_text(strip=True) if time_td else ""
            parsed_time = self._parse_time(time_text)

            id_match = re.search(r"/topic/(\d+)", href)

            house = RawHouse(
                source=self.SOURCE_NAME,
                source_id=id_match.group(1) if id_match else None,
                source_url=href,
                title=title,
                city=city,
                price=self._extract_price(title),
                rent_type=self._detect_rent_type(title),
                publish_time=parsed_time,
                publisher=publisher or None,
                tags=[city, "豆瓣小组"],
                raw_data={
                    "group_id": group_id,
                    "time_text": time_text,
                    "time_semantics": "最后回应时间(豆瓣列表页不展示独立发布时间)",
                    "reply_count": tds[2].get_text(strip=True) if len(tds) > 2 else "",
                },
            )
            houses.append(house)

        return houses, None

    # ---------- 详情 ----------

    async def fetch_detail(self, source_url: str) -> Optional[RawHouse]:
        """获取帖子详情（正文/图片/作者）"""
        try:
            response = await self.get(source_url)
            if response.status_code != 200:
                return None
            if detect_block(response.text):
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            topic_content = soup.select_one(".topic-content")
            description = ""
            images: List[str] = []
            if topic_content:
                for script in topic_content(["script", "style"]):
                    script.decompose()
                description = topic_content.get_text(separator="\n", strip=True)
                for img in topic_content.select("img"):
                    src = img.get("src") or img.get("data-src") or ""
                    if src:
                        images.append(src)

            publisher = ""
            user_card = soup.select_one(".user-card")
            if user_card:
                publisher = user_card.get_text(strip=True)

            return RawHouse(
                source=self.SOURCE_NAME,
                source_url=source_url,
                description=description or None,
                images=images,
                publisher=publisher or None,
            )
        except Exception:
            return None

    # ---------- 解析工具 ----------

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

        for prefix, day_offset in (("今天", 0), ("昨天", 1)):
            if text.startswith(prefix):
                rest = text[len(prefix):].strip()
                try:
                    h, m = map(int, rest.split(":"))
                except ValueError:
                    return now
                value = now.replace(hour=h, minute=m, second=0, microsecond=0)
                return value - timedelta(days=day_offset)

        match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$", text)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            hour = int(match.group(4)) if match.group(4) else 0
            minute = int(match.group(5)) if match.group(5) else 0
            try:
                return datetime(year, month, day, hour, minute)
            except ValueError:
                return now

        match = re.match(r"^(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$", text)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            hour = int(match.group(3)) if match.group(3) else 0
            minute = int(match.group(4)) if match.group(4) else 0
            return _with_year(month, day, hour, minute)

        match = re.match(r"^(\d{1,2}):(\d{2})$", text)
        if match:
            return now.replace(hour=int(match.group(1)), minute=int(match.group(2)),
                               second=0, microsecond=0)

        # 无法识别：返回 None，避免把采集时间误当成发布时间
        return None

    # ---------- 健康检查 ----------

    async def check_health(self) -> dict:
        """真实探针：请求一个已知小组并确认能解析出帖子，而不只是看 HTTP 200"""
        group_id = self.GROUPS["北京"][0]
        url = f"{self.base_url}/{group_id}/discussion"
        try:
            response = await self.get(url)
        except Exception as e:
            self.set_status(STATUS_ERROR, f"{type(e).__name__}: {e}")
            return {"status": STATUS_ERROR, "message": str(e), "verified": False}

        if response.status_code == 429:
            msg = "HTTP 429 被限流，需等待冷却或配置 DOUBAN_COOKIE"
            self.set_status(STATUS_BLOCKED, msg)
            return {"status": STATUS_BLOCKED, "message": msg, "verified": False}

        if response.status_code != 200:
            msg = f"HTTP {response.status_code}"
            self.set_status(STATUS_ERROR, msg)
            return {"status": STATUS_ERROR, "message": msg, "verified": False}

        reason = detect_block(response.text)
        if reason:
            msg = f"豆瓣返回风控中间页（{reason}），配置 DOUBAN_COOKIE 可提高成功率"
            self.set_status(STATUS_BLOCKED, msg)
            return {"status": STATUS_BLOCKED, "message": msg, "verified": False}

        soup = BeautifulSoup(response.text, "html.parser")
        rows = len(soup.select("table.olt tr"))
        if rows == 0:
            msg = "页面正常但未解析到帖子列表（小组 ID 可能失效或页面结构变化）"
            self.set_status(STATUS_UNAVAILABLE, msg)
            return {"status": STATUS_UNAVAILABLE, "message": msg, "verified": False}

        msg = f"可访问，小组 {group_id} 解析到 {rows} 行"
        self.set_status(STATUS_OK, msg)
        return {"status": STATUS_OK, "message": msg, "verified": True}
