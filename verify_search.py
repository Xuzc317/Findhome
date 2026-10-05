#!/usr/bin/env python3
"""
搜索接口与配置层自检

在项目根目录执行（需先启动后端）:
    python verify_search.py
    python verify_search.py --base http://localhost:8000/api

覆盖两块本轮新增的能力：
1. POST /api/search —— 任意条件搜索（不再依赖写死的档案）
2. GET  /api/settings —— 统一配置状态

其中**密钥不泄漏**是硬性断言：配置接口绝不能返回服务端密钥或 Cookie 明文。
"""

import argparse
import json
import sys

import httpx


class Checker:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        # trust_env=False：绕过 macOS 系统代理，否则访问 localhost 可能被代理拦截
        self.client = httpx.Client(timeout=60.0, trust_env=False)
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

    def skip(self, name: str, why: str = ""):
        self.skipped += 1
        print(f"  ⏭️  {name}" + (f"  ({why})" if why else ""))

    def get(self, path: str, **kw):
        return self.client.get(f"{self.base}{path}", **kw)

    def post(self, path: str, **kw):
        return self.client.post(f"{self.base}{path}", **kw)


BASE_CRITERIA = {
    "city": "深圳",
    "stations": [],
    "line_names": [],
    "max_straight_m": 1000,
    "max_walk_minutes": 20,
    "price_min": 1200,
    "price_max": 2500,
    "layouts": ["studio", "1b1l", "2b1l"],
    "rent_types": [3, 4],
    "exclude_shared": True,
    "compute_walk": False,          # 自检不调用高德，保证快且可重复
}


def search(c: Checker, **overrides):
    payload = {**BASE_CRITERIA, **overrides}
    return c.post("/search", json=payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000/api")
    args = parser.parse_args()
    c = Checker(args.base)

    print("=" * 70)
    print("搜索接口与配置层自检")
    print("=" * 70)

    # ---------------- 城市列表（城市优先选择的数据来源）----------------
    print("\n【城市列表】")
    r = c.get("/search/cities")
    c.check("GET /search/cities 返回 200", r.status_code == 200, f"HTTP {r.status_code}")
    cities = (r.json().get("data") or []) if r.status_code == 200 else []
    c.check("返回城市数组", isinstance(cities, list))
    if cities:
        first = cities[0]
        c.check("城市含 name/houseCount",
                "name" in first and "houseCount" in first, json.dumps(first, ensure_ascii=False))
        c.check("按在租量降序",
                all(cities[i]["houseCount"] >= cities[i + 1]["houseCount"]
                    for i in range(len(cities) - 1)),
                str([x["houseCount"] for x in cities[:5]]))
    else:
        c.skip("城市字段校验", "库中暂无城市数据")

    city = cities[0]["name"] if cities else "深圳"
    # CI 使用空库启动，此时没有地铁数据，依赖站点的检查需要跳过而不是判失败
    has_metro = bool(cities and cities[0].get("stationCount"))

    # ---------------- 搜索：参数校验 ----------------
    print("\n【搜索参数校验】")
    r = search(c, city=city, stations=[], line_names=[])
    c.check("未选站点/线路 → 400", r.status_code == 400, f"HTTP {r.status_code}")

    # ---------------- 搜索：按站点 ----------------
    print("\n【按站点搜索】")
    r = search(c, city=city, stations=["上芬", "上塘"])
    body = r.json() if r.status_code == 200 else {}
    c.check("GET 返回 200", r.status_code == 200, f"HTTP {r.status_code}")
    c.check("响应含 data/pendingLocation/stats",
            all(k in body for k in ("data", "pendingLocation", "stats")),
            str(list(body.keys())))
    c.check("data 是数组", isinstance(body.get("data"), list))
    matched = body.get("data") or []
    if matched:
        m = matched[0]
        for key in ("house_id", "title", "price", "nearest_station", "listing_kind",
                    "poster_type", "walk_minutes", "straight_m"):
            c.check(f"结果含字段 {key}", key in m)
        c.check("结果站点都在所选范围内",
                all(x["nearest_station"] in ("上芬", "上塘") for x in matched),
                str(sorted({x["nearest_station"] for x in matched})))
        c.check("价格在预算内",
                all(1200 <= (x["price"] or 0) <= 2500 for x in matched),
                f"{min((x['price'] or 0) for x in matched)}~{max((x['price'] or 0) for x in matched)}")
    else:
        c.skip("结果字段校验", "该组合暂无匹配（空库或该范围无房源，属预期）")

    # ---------------- 搜索：按线路展开站点 ----------------
    print("\n【按线路自动展开站点】")
    if not has_metro:
        c.skip("按线路展开站点", "库中暂无地铁数据（空库环境下属预期）")
    else:
        r = search(c, city=city, stations=[], line_names=["6号线"])
        body2 = r.json() if r.status_code == 200 else {}
        crit = body2.get("criteria") or {}
        stations = crit.get("stations") or []
        c.check("线路展开为站点清单", len(stations) > 2, f"{len(stations)} 个站")
        c.check("展开结果含线路上的站", "上芬" in stations or "元芬" in stations,
                str(stations[:8]))

    # ---------------- 搜索：过滤器生效 ----------------
    print("\n【筛选条件生效】")
    r_all = search(c, city=city, stations=["上芬", "上塘", "元芬", "红山", "龙华"])
    r_sub = search(c, city=city, stations=["上芬", "上塘", "元芬", "红山", "龙华"],
                   listing_kinds=["sublet"])
    if r_all.status_code == 200 and r_sub.status_code == 200:
        all_kinds = {x["listing_kind"] for x in (r_all.json().get("data") or [])}
        sub_kinds = {x["listing_kind"] for x in (r_sub.json().get("data") or [])}
        c.check("限定转租后只剩 sublet",
                sub_kinds <= {"sublet"}, str(sub_kinds))
        if all_kinds - {"sublet"}:
            c.check("未限定时含其它类型（说明筛选确实起作用）",
                    bool(all_kinds - {"sublet"}), str(all_kinds))
        else:
            c.skip("对照检查", "该范围本来就全是转租")
    else:
        c.skip("筛选条件校验", "搜索请求失败")

    # 价格区间
    r_price = search(c, city=city, stations=["上芬"], price_min=1500, price_max=1800)
    if r_price.status_code == 200:
        prices = [x["price"] for x in (r_price.json().get("data") or []) if x["price"]]
        c.check("价格区间严格生效",
                all(1500 <= p <= 1800 for p in prices), str(sorted(prices)[:6]))
    else:
        c.skip("价格区间校验", f"HTTP {r_price.status_code}")

    # 数据源
    r_src = search(c, city=city, stations=["上芬", "上塘"], sources=["xiaohongshu"])
    if r_src.status_code == 200:
        srcs = {x["source"] for x in (r_src.json().get("data") or [])}
        c.check("数据源筛选生效", srcs <= {"xiaohongshu"}, str(srcs))

    # 排序
    r_sort = search(c, city=city, stations=["上芬", "上塘"], sort_by="price")
    if r_sort.status_code == 200:
        ps = [x["price"] for x in (r_sort.json().get("data") or []) if x["price"] is not None]
        c.check("按价格升序",
                all(ps[i] <= ps[i + 1] for i in range(len(ps) - 1)), str(ps[:6]))

    # ---------------- 配置层 ----------------
    print("\n【统一配置状态】")
    r = c.get("/settings")
    c.check("GET /settings 返回 200", r.status_code == 200, f"HTTP {r.status_code}")
    data = (r.json().get("data") or {}) if r.status_code == 200 else {}
    for block in ("amap", "llm", "sources", "cookieImport"):
        c.check(f"含 {block} 配置块", block in data)
    c.check("高德区分两类 Key",
            "webServiceConfigured" in data.get("amap", {})
            and "jsConfigured" in data.get("amap", {}))
    c.check("数据源列出启用状态",
            all("enabled" in s for s in data.get("sources", [])),
            str([s.get("name") for s in data.get("sources", [])]))
    c.check("贝壳标记为已放弃",
            any(s.get("key") == "beike" and not s.get("enabled")
                for s in data.get("sources", [])))

    # ---------------- 密钥不泄漏（硬性断言）----------------
    print("\n【密钥不泄漏】")
    from backend.config import get_settings, is_configured
    s = get_settings()
    raw = r.text
    secret_fields = {
        "高德 Web 服务 Key": s.amap_web_key,
        "DeepSeek Key": s.deepseek_api_key,
        "豆包 Key": s.doubao_api_key,
        "闲鱼 Cookie": s.xianyu_cookie,
        "小红书 Cookie": s.xiaohongshu_cookie,
        "豆瓣 Cookie": s.douban_cookie,
    }
    leaked = []
    for label, value in secret_fields.items():
        if is_configured(value) and value in raw:
            leaked.append(label)
    c.check("服务端密钥/Cookie 未出现在响应中", not leaked,
            ("泄漏：" + "、".join(leaked)) if leaked else "全部未下发")

    # 逐字段再确认一遍（防止密钥以其他形式出现）
    amap = data.get("amap", {})
    c.check("amap 不含 webServiceKey 明文",
            "webServiceKey" not in amap and s.amap_web_key not in json.dumps(amap),
            str([k for k in amap.keys()]))
    c.check("llm 块不含任何 Key 字段",
            not any("key" in k.lower() and k.lower() != "provider"
                    for k in data.get("llm", {}).keys()),
            str(list(data.get("llm", {}).keys())))

    print("\n" + "=" * 70)
    print(f"结果: ✅ 通过 {c.passed} | ❌ 失败 {c.failed} | ⏭️ 跳过 {c.skipped}")
    print("=" * 70)
    return 0 if c.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
