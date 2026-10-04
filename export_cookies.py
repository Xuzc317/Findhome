#!/usr/bin/env python3
"""
从常驻浏览器（browser_daemon.py）导出各平台登录 Cookie 到 .env

为什么需要：
浏览器里登录成功后，登录态只存在于浏览器进程内；而 HTTP 采集器
（豆瓣/贝壳这类直接调接口的）读的是 .env 里的 Cookie。
早先贝壳采集器一直撞登录页，就是因为它是用空 Cookie 启动的。

为什么用 CDP 而不是再开一个浏览器：
`.browser-profile` 同一时间只能被一个 Chromium 进程占用（SingletonLock），
再开一个会失败；通过调试端口接管正在运行的那个才是正确做法，
也不会破坏用户已经建立的会话。

用法:
    python export_cookies.py            # 导出全部
    python export_cookies.py beike      # 只导出贝壳
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.config import ENV_FILE  # noqa: E402

# 平台 -> Cookie 域 / 登录后才会出现的 Cookie / .env 变量名
PLATFORMS = {
    "xianyu": {
        "name": "闲鱼",
        "domains": ("goofish.com", "taobao.com"),
        "login_cookies": ("unb",),
        "env": "XIANYU_COOKIE",
    },
    "xiaohongshu": {
        "name": "小红书",
        "domains": ("xiaohongshu.com",),
        "login_cookies": ("web_session",),
        "env": "XIAOHONGSHU_COOKIE",
    },
    "douban": {
        "name": "豆瓣",
        "domains": ("douban.com",),
        "login_cookies": ("dbcl2",),
        "env": "DOUBAN_COOKIE",
    },
    "beike": {
        "name": "贝壳找房",
        "domains": ("ke.com", "lianjia.com"),
        "login_cookies": ("lianjia_token", "ke_uid"),
        "env": "BEIKE_COOKIE",
    },
}


def mask(value: str) -> str:
    return f"{value[:8]}…{value[-4:]}（{len(value)} 字符）" if len(value) > 16 else "(短)"


def write_env(key: str, value: str) -> None:
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    out, replaced = [], False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    try:
        os.chmod(ENV_FILE, 0o600)
    except OSError:
        pass


async def main() -> int:
    parser = argparse.ArgumentParser(description="从常驻浏览器导出 Cookie 到 .env")
    parser.add_argument("platforms", nargs="*", choices=sorted(PLATFORMS),
                        help="要导出的平台，默认全部")
    parser.add_argument("--port", type=int, default=9222)
    args = parser.parse_args()
    targets = args.platforms or list(PLATFORMS)

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{args.port}")
        except Exception as e:
            print(f"❌ 连不上常驻浏览器（端口 {args.port}）：{type(e).__name__}")
            print("   请先启动：python browser_daemon.py")
            return 1

        if not browser.contexts:
            print("❌ 已连接但拿不到浏览器上下文")
            return 1
        context = browser.contexts[0]
        cookies = await context.cookies()
        print(f"浏览器中共有 {len(cookies)} 个 Cookie\n")

        saved = []
        for key in targets:
            info = PLATFORMS[key]
            names = {c["name"] for c in cookies}
            hit = [n for n in info["login_cookies"] if n in names]
            if not hit:
                print(f"  —  {info['name']:8} 未登录，跳过")
                continue
            picked = {}
            for c in cookies:
                if not any(d in (c.get("domain") or "") for d in info["domains"]):
                    continue
                name = c["name"]
                if name not in picked or len(c.get("path") or "") > len(picked[name].get("path") or ""):
                    picked[name] = c
            cookie = "; ".join(f"{k}={v['value']}" for k, v in sorted(picked.items()))
            if len(cookie) < 30:
                print(f"  ⚠️  {info['name']:8} 有登录证据但 Cookie 过短，跳过")
                continue
            write_env(info["env"], cookie)
            saved.append(key)
            print(f"  ✅ {info['name']:8} → {info['env']}（依据 {('、'.join(hit))}，{mask(cookie)}）")

        print()
        if saved:
            print(f"已写入 .env：{'、'.join(PLATFORMS[k]['name'] for k in saved)}")
            print("下一步可执行：python import_cookie.py --check")
        else:
            print("没有可导出的登录态")
        # 只断开连接，不关闭用户的浏览器
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
