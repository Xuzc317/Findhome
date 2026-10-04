#!/usr/bin/env python3
"""
浏览器常驻服务：一次打开四个平台的登录页，你登录后**挂着别关**，
后续采集脚本通过调试端口接管这个已登录的浏览器。

为什么必须常驻：
平台的部分 Cookie 是**会话级**的（关闭浏览器即失效）。
如果登录后关掉窗口，登录态就丢了，采集又会被弹登录框。
所以这里把浏览器一直开着，采集时直接复用同一个会话。

工作原理：
- 启动带 `--remote-debugging-port` 的 Chromium（有窗口，你能看到并操作）
- 打开 闲鱼 / 小红书 / 豆瓣 / 贝壳 四个标签页
- 之后一直运行，采集脚本用 Playwright 的 connect_over_cdp 连上来操作

安全约定：脚本不读取你在页面上的任何输入，也不处理密码；
只在你登录完成后，通过浏览器已有的会话去搜索房源。

用法:
    python browser_daemon.py                 # 打开四个平台
    python browser_daemon.py xianyu douban   # 只打开指定平台
    python browser_daemon.py --port 9223     # 换端口
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

PROFILE_DIR = os.path.join(PROJECT_ROOT, ".browser-profile")
STATUS_FILE = os.path.join(PROFILE_DIR, "daemon_status.json")
DEFAULT_PORT = 9222

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 平台 -> 登录页 / 登录后才会出现的 Cookie / 提示
PLATFORMS = {
    "xianyu": {
        "name": "闲鱼",
        "url": "https://www.goofish.com/",
        "login_cookies": ("unb",),
        "hint": "点右上角「登录」→ 手机闲鱼 App 扫码",
    },
    "xiaohongshu": {
        "name": "小红书",
        "url": "https://www.xiaohongshu.com/explore",
        "login_cookies": ("web_session",),
        "hint": "页面会弹登录框 → 小红书 App 扫码",
    },
    "douban": {
        "name": "豆瓣",
        "url": "https://accounts.douban.com/passport/login",
        "login_cookies": ("dbcl2",),
        "hint": "豆瓣 App 扫码，或用短信验证码",
    },
    "beike": {
        "name": "贝壳找房",
        "url": "https://sz.zu.ke.com/zufang",
        "login_cookies": ("lianjia_token", "ke_uid"),
        "hint": "点右上角「登录/注册」→ 贝壳 App 扫码",
    },
}

BANNER_ID = "__daemon_banner"


async def inject_banner(page, text: str, color: str = "#00a3ca"):
    try:
        await page.evaluate(
            """([id, text, color]) => {
                let el = document.getElementById(id);
                if (!el) {
                    el = document.createElement('div');
                    el.id = id;
                    document.body.appendChild(el);
                }
                el.textContent = text;
                Object.assign(el.style, {
                    position: 'fixed', top: '0', left: '0', right: '0',
                    zIndex: 2147483647, background: color, color: '#fff',
                    font: '600 15px/1.6 -apple-system, "PingFang SC", sans-serif',
                    padding: '10px 16px', textAlign: 'center',
                    boxShadow: '0 2px 8px rgba(0,0,0,.25)', pointerEvents: 'none'
                });
            }""",
            [BANNER_ID, text, color],
        )
    except Exception:
        pass


async def login_status(context) -> dict:
    """检查各平台是否已登录（依据登录后才会出现的 Cookie）"""
    try:
        cookies = await context.cookies()
    except Exception:
        return {}
    names = {c["name"] for c in cookies}
    result = {}
    for key, info in PLATFORMS.items():
        hit = [n for n in info["login_cookies"] if n in names]
        result[key] = {"name": info["name"], "loggedIn": bool(hit),
                       "evidence": hit}
    return result


def write_status(payload: dict) -> None:
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


async def main() -> int:
    parser = argparse.ArgumentParser(description="常驻浏览器：登录四个平台并保持会话")
    parser.add_argument("platforms", nargs="*", choices=sorted(PLATFORMS),
                        help="要打开的平台，默认全部")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"调试端口（默认 {DEFAULT_PORT}）")
    parser.add_argument("--headless", action="store_true",
                        help="无窗口运行（首次登录不要用这个）")
    args = parser.parse_args()

    targets = args.platforms or list(PLATFORMS)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ 未安装 playwright：pip install playwright && python -m playwright install chromium")
        return 1

    os.makedirs(PROFILE_DIR, exist_ok=True)

    print("=" * 74, flush=True)
    print("常驻浏览器启动中…… 请稍候，窗口会自动打开四个标签页", flush=True)
    print("=" * 74, flush=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=args.headless,
            viewport={"width": 1360, "height": 900},
            user_agent=UA,
            locale="zh-CN",
            args=[
                f"--remote-debugging-port={args.port}",
                "--window-position=40,40",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        pages = {}
        for key in targets:
            info = PLATFORMS[key]
            page = await context.new_page()
            pages[key] = page
            try:
                await page.goto(info["url"], wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print(f"  ⚠️ {info['name']} 打开失败：{type(e).__name__}: {str(e)[:60]}", flush=True)

        print(f"\n✅ 浏览器已就绪，调试端口 {args.port}", flush=True)
        print(f"   标签页：{'、'.join(PLATFORMS[k]['name'] for k in targets)}", flush=True)
        for key in targets:
            info = PLATFORMS[key]
            print(f"     · {info['name']}：{info['hint']}", flush=True)
        print("\n   登录完成后**不要关闭这个浏览器窗口**，它在后台保持登录态。", flush=True)
        print("   我会通过调试端口接管它来搜索房源。\n", flush=True)

        last_report = ""
        started = time.time()
        while True:
            status = await login_status(context)
            for key, page in pages.items():
                if page.is_closed():
                    continue
                info = PLATFORMS[key]
                if status.get(key, {}).get("loggedIn"):
                    await inject_banner(
                        page, f"✅ {info['name']} 已登录（保持窗口打开即可）", "#52c41a")
                else:
                    await inject_banner(
                        page, f"登录助手：请登录【{info['name']}】—— {info['hint']}"
                              f"（登录后保持窗口打开）")

            summary = " | ".join(
                f"{info['name']}{'✅' if status.get(k, {}).get('loggedIn') else '—'}"
                for k, info in PLATFORMS.items() if k in pages)
            if summary != last_report:
                last_report = summary
                print(f"[{int(time.time() - started)}s] 登录状态: {summary}", flush=True)

            write_status({
                "port": args.port,
                "startedAt": started,
                "updatedAt": time.time(),
                "platforms": status,
                "profileDir": PROFILE_DIR,
            })
            await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n已停止常驻浏览器")
