#!/usr/bin/env python3
"""
HouseSearch Local v1 - 后端 API 自检脚本

在项目根目录执行（需先启动后端）:
    python verify_api.py
    python verify_api.py --base http://localhost:8000/api

逐项检查接口契约（尤其是前端依赖的 {"code":0,"data":[...]} 响应体形状），
输出 PASS/FAIL 汇总，退出码 0 表示全部通过。
"""

import argparse
import sys

import httpx


class Checker:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        # trust_env=False：绕过 macOS 系统代理，否则访问 localhost 可能被代理拦截返回 502
        self.client = httpx.Client(timeout=15.0, trust_env=False)
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def check(self, name: str, condition: bool, detail: str = ""):
        if condition:
            self.passed += 1
            print(f"  ✅ {name}" + (f"  ({detail})" if detail else ""))
        else:
            self.failed += 1
            print(f"  ❌ {name}" + (f"  ({detail})" if detail else ""))

    def get(self, path: str, **kwargs):
        return self.client.get(f"{self.base}{path}", **kwargs)

    def post(self, path: str, **kwargs):
        return self.client.post(f"{self.base}{path}", **kwargs)

    def section(self, title: str):
        print(f"\n{title}")


def safe_json(response) -> dict:
    """容错解析：接口异常时返回 {} 而不是抛异常中断整个自检"""
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="后端 API 自检")
    parser.add_argument("--base", default="http://127.0.0.1:8000/api", help="API 根地址")
    args = parser.parse_args()

    c = Checker(args.base)

    # ---- 连通性 ----
    c.section("【连通性】")
    try:
        r = c.get("/health")
        c.check("GET /api/health", r.status_code == 200 and safe_json(r).get("status") == "ok",
                f"HTTP {r.status_code}")
    except Exception as e:
        print(f"  ❌ 无法连接后端 {args.base}: {e}")
        print("\n请先启动后端: python start.py backend")
        return 1

    # ---- 房源搜索（前端列表页依赖）----
    c.section("【房源搜索 /v3/houses】")
    r = c.get("/v3/houses", params={"pageSize": 3})
    body = safe_json(r)
    c.check("响应含 code 字段", body.get("code") == 0)
    c.check("响应含 data 数组（前端会二次取 .data）", isinstance(body.get("data"), list),
            f"{len(body.get('data') or [])} 条")
    c.check("响应含 total", isinstance(body.get("total"), int), f"total={body.get('total')}")
    c.check("pageSize 参数被正确识别", body.get("pageSize") == 3, f"pageSize={body.get('pageSize')}")

    items = body.get("data") or []
    if items:
        keys = {"id", "title", "price", "city", "source", "displaySource", "onlineURL",
                "pictures", "rentType", "publishDate", "longitude", "latitude"}
        missing = keys - set(items[0].keys())
        c.check("列表项字段满足前端 HouseListItem", not missing, f"缺失={missing or '无'}")
    else:
        c.skipped += 1
        print("  ⏭️  列表为空，跳过字段校验（先执行 python crawl.py douban --city 北京）")

    # camelCase 筛选
    r = c.get("/v3/houses", params={"fromPrice": 1000, "toPrice": 99999999, "pageSize": 50})
    camel_total = safe_json(r).get("total")
    c.check("camelCase 价格筛选生效", isinstance(camel_total, int),
            f"fromPrice=1000 时 total={camel_total}")

    r = c.get("/v3/houses", params={"pageSize": 50, "hide_duplicates": "false"})
    with_dup = safe_json(r).get("total")
    r = c.get("/v3/houses", params={"pageSize": 50, "hide_duplicates": "true"})
    without_dup = safe_json(r).get("total")
    c.check("去重过滤生效（hide_duplicates）", with_dup >= without_dup,
            f"含重复={with_dup} 隐藏后={without_dup}")

    r = c.get("/v3/houses", params={"sortBy": "price", "sortOrder": "asc", "pageSize": 10})
    prices = [h["price"] for h in (safe_json(r).get("data") or []) if h.get("price")]
    c.check("按价格升序排序", prices == sorted(prices), f"prices={prices[:6]}")

    # ---- 城市接口（前端筛选栏依赖）----
    c.section("【城市 /v2/cities】")
    r = c.get("/v2/cities", params={"fields": "id,city,sources"})
    body = safe_json(r)
    cities = body.get("data") or []
    c.check("返回 code=0", body.get("code") == 0)
    c.check("城市列表非空（空库也要有默认城市）", len(cities) > 0, f"{len(cities)} 个城市")
    if cities:
        c.check("城市项含 sources 数组（前端会 unshift 全部）",
                isinstance(cities[0].get("sources"), list),
                f"如 {cities[0].get('city')}: {[s.get('source') for s in cities[0].get('sources', [])]}")

    r = c.get("/v2/cities/上海/districts")
    c.check("GET /v2/cities/{city}/districts", r.status_code == 200 and "data" in safe_json(r))

    # ---- 地图 / 详情 ----
    c.section("【地图与详情】")
    r = c.post("/v2/houses", json={"city": "上海", "intervalDay": 30, "size": 1200})
    body = safe_json(r)
    c.check("POST /v2/houses 返回 data 数组", isinstance(body.get("data"), list),
            f"{len(body.get('data') or [])} 条")

    target_id = None
    r = c.get("/v3/houses", params={"pageSize": 1})
    data = safe_json(r).get("data") or []
    if data:
        target_id = data[0]["id"]

    if target_id:
        r = c.get(f"/v2/houses/{target_id}")
        body = safe_json(r)
        c.check("GET /v2/houses/{id} 返回 data.title",
                body.get("success") and body.get("data", {}).get("title") is not None)

        r = c.get(f"/houses/{target_id}/risk")
        body = safe_json(r)
        scores = (body.get("data") or {}).get("scores") or {}
        c.check("GET /api/houses/{id}/risk 返回三维评分",
                {"agent", "ad", "suspicious"} <= set(scores), f"{scores}")
    else:
        c.skipped += 1
        print("  ⏭️  无房源数据，跳过详情/风险校验")

    # ---- 数据源与配置 ----
    c.section("【数据源与配置】")
    r = c.get("/sources")
    raw_sources = safe_json(r)
    # /api/sources 返回的是 JSON 数组本身
    sources = raw_sources if isinstance(raw_sources, list) else (raw_sources.get("data") or [])
    c.check("GET /api/sources 返回列表", r.status_code == 200 and len(sources) > 0,
            f"{[s.get('source') for s in sources if isinstance(s, dict)]}")
    c.check("数据源含 needs_login 标记",
            all("needs_login" in s for s in sources) if sources else False)

    r = c.get("/houses/sources/count")
    c.check("GET /api/houses/sources/count", r.status_code == 200 and "data" in safe_json(r),
            str(safe_json(r).get("data")))

    r = c.get("/config")
    c.check("GET /api/config 返回 amapKey 字段",
            "amapKey" in (safe_json(r).get("data") or {}))

    r = c.get("/crawl/logs", params={"limit": 5})
    c.check("GET /api/crawl/logs", r.status_code == 200 and isinstance(safe_json(r).get("data"), list))

    # ---- 汇总 ----
    print("\n" + "=" * 52)
    print(f"结果: ✅ 通过 {c.passed} 项 | ❌ 失败 {c.failed} 项 | ⏭️  跳过 {c.skipped} 项")
    print("=" * 52)

    if c.failed:
        print("\n存在失败项，请检查后端日志。")
        return 1

    print("\n后端 API 契约与前端预期一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
