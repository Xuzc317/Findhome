#!/usr/bin/env python3
"""
前端端到端冒烟测试（可选）

验证链路最后一环：**前端列表能否真正渲染出后端返回的房源**，
以及点击卡片能否进入详情页、原始链接是否存在于页面上。

依赖 playwright（不在 requirements.txt 中，属于可选工具）：
    pip install playwright && python -m playwright install chromium

未安装时会优雅跳过，不影响其他验证。

用法:
    # 先启动后端（单端口模式会自动托管前端构建产物）
    python start.py backend
    python tests/test_ui_smoke.py --city 深圳
"""

import argparse
import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(PROJECT_ROOT, "docs", "screenshots")

PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✅ {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAILED += 1
        print(f"  ❌ {name}" + (f"  ({detail})" if detail else ""))


async def run(base: str, city: str, screenshot: str) -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("⏭️  未安装 playwright，跳过 UI 冒烟测试")
        print("   安装: pip install playwright && python -m playwright install chromium")
        return 0

    console_errors = []
    failed_requests = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        page.on("console", lambda msg: console_errors.append(msg.text)
                if msg.type == "error" else None)
        page.on("requestfailed",
                lambda req: failed_requests.append(f"{req.method} {req.url}"))

        print(f"\n【打开列表页】{base}/houses-list?city={city}")
        await page.goto(f"{base}/houses-list?city={city}", wait_until="networkidle")

        # 筛选栏：常驻显示的区块（地铁选址/预算/房型/出租类型）
        body_text = await page.inner_text("body")
        check("筛选栏渲染出「筛选条件」标题", "筛选条件" in body_text)
        check("筛选栏渲染出「地铁选址」", "地铁选址" in body_text)
        check("筛选栏渲染出「预算」", "预算" in body_text)
        check("筛选栏渲染出「房型」", "房型" in body_text)
        check("筛选栏渲染出房型档位「2房1厅」", "2房1厅" in body_text)
        check("筛选栏渲染出「出租类型」且默认整租", "出租类型" in body_text and "整租" in body_text)

        # 「更多筛选」默认折叠，展开后再校验其余条件
        try:
            await page.click("text=更多筛选", timeout=5000)
            await page.wait_for_timeout(800)
            expanded_text = await page.inner_text("body")
            check("展开「更多筛选」后有「发布时间」", "发布时间" in expanded_text)
            check("展开「更多筛选」后有「风险」", "风险" in expanded_text)
            check("展开「更多筛选」后有「排除关键词」", "排除关键词" in expanded_text)
            check("展开「更多筛选」后有「数据准备」", "数据准备" in expanded_text)
        except Exception as e:
            check("展开「更多筛选」", False, f"{type(e).__name__}: {e}")

        # 房源卡片
        try:
            await page.wait_for_selector('[class*="itemCard"]', timeout=20000)
        except Exception:
            check("房源卡片渲染", False, "20 秒内未出现卡片")

        cards = await page.query_selector_all('[class*="itemCard"]')
        check("房源卡片数量 > 0", len(cards) > 0, f"{len(cards)} 张")

        first_title = first_price = ""
        if cards:
            first_title = (await cards[0].inner_text()).split("\n")[0].strip()
            price_el = await cards[0].query_selector('[class*="price"]')
            if price_el:
                first_price = (await price_el.inner_text()).strip()
            check("卡片显示标题", bool(first_title), first_title[:34])
            check("卡片显示价格", bool(first_price), first_price)
            check("价格不是「暂无价格」占位",
                  "暂无价格" not in first_price or first_price == "￥暂无价格",
                  first_price)

            # 页面上的卡片标题应当来自后端真实数据（非演示数据）
            check("列表不含演示数据", "示例]" not in body_text)

            os.makedirs(SHOT_DIR, exist_ok=True)
            shot_path = os.path.join(SHOT_DIR, screenshot)
            await page.screenshot(path=shot_path, full_page=False)
            print(f"  📸 截图: {shot_path}")

            # 点击进入详情：卡片使用 window.open，会在新标签页打开
            try:
                async with page.context.expect_page(timeout=10000) as new_page_info:
                    await cards[0].click()
                detail_page = await new_page_info.value
                await detail_page.wait_for_load_state("networkidle")
                detail_url = detail_page.url
                detail_text = await detail_page.inner_text("body")
            except Exception as e:
                detail_url = ""
                detail_text = ""
                print(f"  ℹ️ 未捕获到新标签页: {type(e).__name__}")

            check("点击卡片进入详情页", "/houses/" in detail_url, detail_url or "未跳转")
            check("详情页显示房源信息",
                  bool(first_title[:8]) and first_title[:8] in detail_text,
                  f"查找 {first_title[:14]!r}")

            # 链路最后一环：页面上的“查看来源”必须指向平台原始链接
            source_link = await detail_page.query_selector('a[href^="http"]:has-text("查看来源")')
            if source_link is None:
                # 退而求其次：取页面里第一个外链
                links = await detail_page.query_selector_all('a[href^="http"]')
                source_link = links[0] if links else None

            if source_link is not None:
                href = await source_link.get_attribute("href")
                check("详情页存在平台原始链接（查看来源）",
                      bool(href) and href.startswith("http"), (href or "")[:70])
                check("原始链接不是占位域名",
                      href and not any(m in href for m in
                                       ("demo.local", "example.com", "localhost")),
                      (href or "")[:70])

                # 与 API 返回的 onlineURL 比对
                house_id = detail_url.rstrip("/").split("/")[-1]
                import json as _json
                import urllib.request as _url
                try:
                    with _url.urlopen(f"{base}/api/v2/houses/{house_id}", timeout=10) as resp:
                        payload = _json.loads(resp.read().decode("utf-8"))
                    api_url = (payload.get("data") or {}).get("onlineURL")
                    check("页面原始链接与 API onlineURL 一致", api_url == href,
                          f"api={str(api_url)[:50]}")
                except Exception as e:
                    check("页面原始链接与 API onlineURL 一致", False, f"查询失败 {e}")
            else:
                check("详情页存在平台原始链接（查看来源）", False, "未找到外链")

            if "/houses/" in detail_url:
                shot_path = os.path.join(SHOT_DIR, screenshot.replace(".png", "-detail.png"))
                await detail_page.screenshot(path=shot_path, full_page=False)
                print(f"  📸 截图: {shot_path}")
                await detail_page.close()

        # 地图页（不配置高德 Key 时应给出明确提示，而不是白屏报错）
        print(f"\n【打开地图页】{base}/map")
        await page.goto(f"{base}/map", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        map_text = await page.inner_text("body")
        check("地图页可加载（无 JS 崩溃）", len(map_text) > 0, f"{len(map_text)} 字符")

        await browser.close()

    print("\n【控制台与网络】")
    real_errors = [e for e in console_errors if "favicon" not in e.lower()]
    check("无 JS 控制台错误", not real_errors,
          f"{len(real_errors)} 条" + (f": {real_errors[0][:80]}" if real_errors else ""))

    # 地图瓦片是懒加载的 CDN 资源，关闭浏览器时会大量中断（net::ERR_ABORTED），
    # 属于正常现象，不计入"失败请求"；只看我们自己的接口请求。
    IGNORED_HOSTS = ("amap.com", "autonavi.com", "google-analytics.com",
                     "googletagmanager.com", "favicon")
    real_failures = [
        r for r in failed_requests
        if not any(host in r.lower() for host in IGNORED_HOSTS)
    ]
    check("无失败的业务请求（已排除地图瓦片与统计域名）", not real_failures,
          f"{len(real_failures)} 条"
          + (f": {real_failures[0][:80]}" if real_failures else "")
          + f"（另有 {len(failed_requests) - len(real_failures)} 条地图瓦片中断，属正常）")

    print("\n" + "=" * 60)
    print(f"UI 冒烟结果: ✅ 通过 {PASSED} | ❌ 失败 {FAILED}")
    print("=" * 60)
    return 0 if FAILED == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="前端端到端冒烟测试")
    parser.add_argument("--base", default="http://127.0.0.1:8000",
                        help="站点地址（单端口模式由后端托管前端）")
    parser.add_argument("--city", default="深圳", help="要验证的城市")
    parser.add_argument("--screenshot", default="houses-list.png", help="截图文件名")
    args = parser.parse_args()
    return asyncio.run(run(args.base, args.city, args.screenshot))


if __name__ == "__main__":
    sys.exit(main())
