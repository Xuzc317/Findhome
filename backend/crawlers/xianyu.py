"""
闲鱼（Goofish）租房爬虫

实测结论（2026-10-04）：
- 旧接口 https://s.2.taobao.com/list/ 已下线，会 302 到 deny_pc.html（封禁页）。
- www.goofish.com/search 是纯客户端渲染 SPA，HTML 内不含任何商品数据。
- 搜索接口 mtop.taobao.idlemtopsearch.pc.search 未登录时返回：
      ret = ["RGV587_ERROR::SM::哎哟喂,被挤爆啦,请稍后重试!"]
      data.url -> https://passport.goofish.com/mini_login.htm...
  即平台要求登录。
- 该接口还要求 x-sign 等由页面 JS 生成的签名参数；本 Adapter 不做签名逆向
  （属于绕过访问控制），因此仅在用户提供本人登录 Cookie 时尝试请求，
  并把平台返回的真实结果如实上报，不伪造数据。

结论：需要用户本人浏览器登录后的 Cookie（XIANYU_COOKIE）。
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

# 关键词式平台，不依赖城市路径
GENERIC_CITIES = {
    "北京": "北京", "上海": "上海", "深圳": "深圳", "广州": "广州",
    "杭州": "杭州", "成都": "成都", "武汉": "武汉", "西安": "西安",
    "南京": "南京", "重庆": "重庆", "苏州": "苏州", "天津": "天津",
}


class XianyuCrawler(BaseCrawler):
    """闲鱼爬虫（需要登录 Cookie）"""

    SOURCE_NAME = "xianyu"
    DISPLAY_NAME = "闲鱼"
    NEEDS_LOGIN = True
    MIN_REQUEST_INTERVAL = 6.0

    SUPPORTED_CITIES = GENERIC_CITIES

    SEARCH_API = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/"

    DETAIL_AVAILABLE = False
    DETAIL_UNAVAILABLE_REASON = "闲鱼详情页同样要求登录态与签名参数，未实现"

    def __init__(self, cookie: str = ""):
        super().__init__(cookie=cookie)
        self.last_platform_message: str = ""

    # ---------- 采集 ----------

    async def search(self, city: str, keyword: str = "", page: int = 1) -> List[RawHouse]:
        """搜索闲鱼在租房源

        未配置 Cookie 时不会发起无效请求，直接返回 needs_login，
        避免把“空结果”误报成“该城市没有房源”。
        """
        if not self.has_cookie:
            self.set_status(
                STATUS_NEEDS_LOGIN,
                "未配置 XIANYU_COOKIE：闲鱼搜索接口未登录时返回 RGV587_ERROR 并跳转 passport 登录页。"
                "请从本人浏览器登录后复制 Cookie 到 .env。",
            )
            return []

        query = f"{city} 租房"
        if keyword:
            query = f"{city} {keyword}"

        params = {
            "jsv": "2.7.2",
            "appKey": "34839810",
            "t": str(int(datetime.now().timestamp() * 1000)),
            "v": "1.0",
            "type": "originaljson",
            "accountSite": "xianyu",
            "dataType": "json",
            "timeout": "20000",
            "api": "mtop.taobao.idlemtopsearch.pc.search",
            "sessionOption": "AutoLoginOnly",
        }
        data = {"q": query, "pageNumber": str(page), "rowsPerPage": "30"}

        try:
            # 注意：使用 get() 以复用限速逻辑
            await self.polite_sleep()
            response = await self.client.post(self.SEARCH_API, params=params, data=data)
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
            self.set_status(STATUS_UNAVAILABLE, "接口返回非 JSON（可能被重定向到登录页）")
            return []

        ret = payload.get("ret") or []
        ret_text = " ".join(str(x) for x in ret)
        self.last_platform_message = ret_text

        lowered = ret_text.upper()
        if "RGV587" in lowered or "FAIL_SYS" in lowered or "登录" in ret_text:
            self.set_status(
                STATUS_NEEDS_LOGIN,
                f"平台拒绝：{ret_text[:120]}（登录态失效或缺少签名参数）",
            )
            return []

        if "SUCCESS" not in lowered:
            self.set_status(STATUS_UNAVAILABLE, f"平台返回未知结果：{ret_text[:120]}")
            return []

        houses = self._parse_results(payload, city)
        if not houses:
            self.set_status(STATUS_EMPTY, "接口调用成功但未解析到房源（字段结构可能变化）")
            return []

        self.set_status(STATUS_OK, f"解析到 {len(houses)} 条")
        return houses

    def _parse_results(self, payload: dict, city: str) -> List[RawHouse]:
        """解析 mtop 搜索响应（字段缺失即留空，不猜测）"""
        result_list = (((payload.get("data") or {}).get("resultList")) or [])
        houses: List[RawHouse] = []

        for entry in result_list:
            try:
                item = ((entry.get("data") or {}).get("item")) or {}
                main = item.get("main") or {}
                ex = main.get("exContent") or {}

                item_id = (main.get("clickParam") or {}).get("args", {}).get("item_id") \
                    or ex.get("itemId") or item.get("itemId")
                title = ex.get("title") or ""
                if not title or not item_id:
                    continue

                # 价格：detailParams.price 是字符串，形如 "2500"
                price = None
                raw_price = ((ex.get("detailParams") or {}).get("price")
                             or (ex.get("priceInfo") or {}).get("price"))
                if raw_price is not None:
                    try:
                        price = int(float(str(raw_price).replace(",", "")))
                    except ValueError:
                        price = extract_price(str(raw_price))
                if price is None:
                    price = extract_price(title)

                # 发布时间：部分卡片不带该字段
                publish_time = None
                args = (main.get("clickParam") or {}).get("args") or {}
                for key in ("publishTime", "publish_time"):
                    if args.get(key):
                        try:
                            publish_time = datetime.fromtimestamp(int(args[key]) / 1000)
                        except (ValueError, TypeError, OSError):
                            publish_time = None
                        break

                images = []
                pic = (ex.get("picUrl") or (ex.get("imageInfos") or [{}])[0].get("url"))
                if pic:
                    images.append(pic)

                houses.append(RawHouse(
                    source=self.SOURCE_NAME,
                    source_id=str(item_id),
                    source_url=f"https://www.goofish.com/item?id={item_id}",
                    title=title,
                    city=city,
                    price=price,
                    publish_time=publish_time,
                    images=images,
                    tags=[city, "闲鱼"],
                    raw_data={"ret": self.last_platform_message},
                ))
            except Exception:
                continue

        return houses

    # ---------- 健康检查 ----------

    async def check_health(self) -> dict:
        """真实探针：调用搜索接口并如实上报平台响应"""
        if not self.has_cookie:
            msg = ("未配置 XIANYU_COOKIE：平台要求登录"
                   "（未登录返回 RGV587_ERROR 并跳转 passport.goofish.com）")
            self.set_status(STATUS_NEEDS_LOGIN, msg)
            return {"status": STATUS_NEEDS_LOGIN, "message": msg, "verified": True}

        try:
            await self.polite_sleep()
            response = await self.client.post(
                self.SEARCH_API,
                params={"jsv": "2.7.2", "appKey": "34839810", "v": "1.0",
                        "type": "originaljson", "dataType": "json",
                        "api": "mtop.taobao.idlemtopsearch.pc.search"},
                data={"q": "北京租房", "pageNumber": "1", "rowsPerPage": "5"},
            )
            self._last_request_at = datetime.now()
            payload = response.json()
            ret_text = " ".join(str(x) for x in (payload.get("ret") or []))
        except Exception as e:
            self.set_status(STATUS_ERROR, f"{type(e).__name__}: {e}")
            return {"status": STATUS_ERROR, "message": str(e), "verified": False}

        if "SUCCESS" in ret_text.upper():
            msg = f"接口可用：{ret_text[:80]}"
            self.set_status(STATUS_OK, msg)
            return {"status": STATUS_OK, "message": msg, "verified": True}

        msg = f"平台返回：{ret_text[:120] or '空响应'}（登录态失效或缺少签名参数）"
        self.set_status(STATUS_NEEDS_LOGIN, msg)
        return {"status": STATUS_NEEDS_LOGIN, "message": msg, "verified": True}
