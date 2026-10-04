"""
小红书租房爬虫

实测结论（2026-10-04）：
- GET  /api/sns/web/v1/search/notes  → HTTP 500 "create invoker failed"（方法/参数不对）
- POST /api/sns/web/v1/search/notes  → HTTP 200
      {"code":-101,"success":false,"msg":"无登录信息，或登录信息为空"}
  即平台明确要求登录。
- /search_result 页面为客户端渲染：HTML 内 __INITIAL_STATE__ 只有全局配置，
  0 条笔记链接，无法从 HTML 直接解析搜索结果。
- 小红书 Web 接口还要求 x-s / x-t 签名头（由页面 JS 生成）。
  本 Adapter 不做签名逆向（属于绕过访问控制）。

结论：需要用户本人浏览器登录后的 Cookie（XIAOHONGSHU_COOKIE）。
未配置时明确上报 needs_login，不做无限试探；配置后尝试请求并如实上报结果。
"""

from datetime import datetime
from typing import List, Optional

from backend.crawlers.base import (
    STATUS_EMPTY,
    STATUS_ERROR,
    STATUS_NEEDS_LOGIN,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    BaseCrawler,
    RawHouse,
    extract_price,
)

GENERIC_CITIES = {
    "北京": "北京", "上海": "上海", "深圳": "深圳", "广州": "广州",
    "杭州": "杭州", "成都": "成都", "武汉": "武汉", "西安": "西安",
    "南京": "南京", "重庆": "重庆", "苏州": "苏州", "天津": "天津",
}


class XiaohongshuCrawler(BaseCrawler):
    """小红书爬虫（需要登录 Cookie）"""

    SOURCE_NAME = "xiaohongshu"
    DISPLAY_NAME = "小红书"
    NEEDS_LOGIN = True
    MIN_REQUEST_INTERVAL = 8.0

    SUPPORTED_CITIES = GENERIC_CITIES

    SEARCH_API = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
    HOME_URL = "https://www.xiaohongshu.com/explore"

    DETAIL_AVAILABLE = False
    DETAIL_UNAVAILABLE_REASON = "笔记详情接口同样要求登录态与签名头，未实现"

    def _api_headers(self) -> dict:
        return {
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.xiaohongshu.com",
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "application/json, text/plain, */*",
        }

    # ---------- 采集 ----------

    async def search(self, city: str, keyword: str = "", page: int = 1) -> List[RawHouse]:
        if not self.has_cookie:
            self.set_status(
                STATUS_NEEDS_LOGIN,
                "未配置 XIAOHONGSHU_COOKIE：搜索接口返回 code=-101「无登录信息，或登录信息为空」。"
                "请从本人浏览器登录后复制 Cookie 到 .env。",
            )
            return []

        query = f"{city} 租房"
        if keyword:
            query = f"{city} {keyword}"

        body = {
            "keyword": query,
            "page": page,
            "page_size": 20,
            "search_id": "",
            "sort": "general",
            "note_type": 0,
        }

        try:
            await self.polite_sleep()
            response = await self.client.post(
                self.SEARCH_API, json=body, headers=self._api_headers()
            )
            self._last_request_at = datetime.now()
        except Exception as e:
            self.set_status(STATUS_ERROR, f"{type(e).__name__}: {e}")
            return []

        if response.status_code != 200:
            self.set_status(STATUS_ERROR, f"HTTP {response.status_code}")
            return []

        try:
            payload = response.json()
        except Exception:
            self.set_status(STATUS_UNAVAILABLE, "接口返回非 JSON")
            return []

        code = payload.get("code")
        if code in (-101, -100):
            self.set_status(
                STATUS_NEEDS_LOGIN,
                f"平台返回 code={code}：{payload.get('msg', '')}（登录态失效）",
            )
            return []

        if not payload.get("success"):
            self.set_status(
                STATUS_UNAVAILABLE,
                f"平台返回 code={code}：{payload.get('msg', '')}"
                "（可能缺少 x-s/x-t 签名头，未做签名逆向）",
            )
            return []

        houses = self._parse_results(payload, city)
        if not houses:
            self.set_status(STATUS_EMPTY, "接口成功但未解析到笔记（字段结构可能变化）")
            return []

        self.set_status(STATUS_OK, f"解析到 {len(houses)} 条")
        return houses

    def _parse_results(self, payload: dict, city: str) -> List[RawHouse]:
        """解析笔记搜索结果（字段缺失即留空）"""
        items = ((payload.get("data") or {}).get("items")) or []
        houses: List[RawHouse] = []

        for entry in items:
            try:
                note_id = entry.get("id") or entry.get("note_id")
                card = entry.get("note_card") or {}
                title = card.get("display_title") or card.get("title") or ""
                desc = card.get("desc") or ""
                if not note_id:
                    continue
                if not title and not desc:
                    continue

                # 价格：标题/正文里带价格语境才提取，否则留空
                price = extract_price(f"{title} {desc}")

                publisher = (card.get("user") or {}).get("nickname") or None

                images = []
                cover = card.get("cover") or {}
                if cover.get("url_default"):
                    images.append(cover["url_default"])
                for img in (card.get("image_list") or [])[:3]:
                    url = img.get("url_default") or img.get("url")
                    if url:
                        images.append(url)

                # 发布时间：接口未直接给出时留空（不猜测）
                publish_time = None
                if card.get("time"):
                    try:
                        publish_time = datetime.fromtimestamp(int(card["time"]) / 1000)
                    except (ValueError, TypeError, OSError):
                        publish_time = None

                houses.append(RawHouse(
                    source=self.SOURCE_NAME,
                    source_id=str(note_id),
                    source_url=f"https://www.xiaohongshu.com/explore/{note_id}",
                    title=(title or desc[:40] or "小红书租房笔记"),
                    description=desc or None,
                    city=city,
                    price=price,
                    rent_type=self._detect_rent_type(f"{title} {desc}"),
                    publish_time=publish_time,
                    publisher=publisher,
                    images=images,
                    tags=[city, "小红书"],
                    raw_data={"note_id": note_id},
                ))
            except Exception:
                continue

        return houses

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

    # ---------- 健康检查 ----------

    async def check_health(self) -> dict:
        """真实探针：调用搜索接口并如实上报平台响应"""
        if not self.has_cookie:
            msg = ("未配置 XIAOHONGSHU_COOKIE：搜索接口返回 code=-101"
                   "「无登录信息，或登录信息为空」，页面为客户端渲染且需 x-s/x-t 签名头")
            self.set_status(STATUS_NEEDS_LOGIN, msg)
            return {"status": STATUS_NEEDS_LOGIN, "message": msg, "verified": True}

        try:
            await self.polite_sleep()
            response = await self.client.post(
                self.SEARCH_API,
                json={"keyword": "北京租房", "page": 1, "page_size": 5,
                      "search_id": "", "sort": "general", "note_type": 0},
                headers=self._api_headers(),
            )
            self._last_request_at = datetime.now()
            payload = response.json()
        except Exception as e:
            self.set_status(STATUS_ERROR, f"{type(e).__name__}: {e}")
            return {"status": STATUS_ERROR, "message": str(e), "verified": False}

        code = payload.get("code")
        if code in (-101, -100):
            msg = f"平台返回 code={code}：{payload.get('msg', '')}（登录态失效）"
            self.set_status(STATUS_NEEDS_LOGIN, msg)
            return {"status": STATUS_NEEDS_LOGIN, "message": msg, "verified": True}

        if payload.get("success"):
            msg = "接口可用，已返回数据"
            self.set_status(STATUS_OK, msg)
            return {"status": STATUS_OK, "message": msg, "verified": True}

        msg = f"平台返回 code={code}：{payload.get('msg', '')}"
        self.set_status(STATUS_UNAVAILABLE, msg)
        return {"status": STATUS_UNAVAILABLE, "message": msg, "verified": True}
