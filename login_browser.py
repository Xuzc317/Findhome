#!/usr/bin/env python3
"""
登录助手：打开浏览器让你自己登录，自动把 Cookie 存进 .env

为什么这样做：
闲鱼 / 小红书必须登录，豆瓣带登录态后也稳定得多。手工去开发者工具里
复制 Cookie 又长又容易漏字段，所以这里直接开一个浏览器窗口，
你在里面用**扫码 / 短信验证码**正常登录，脚本检测到登录成功后
自动把 Cookie 写入 `.env`（已被 gitignore）。

安全约定：
- **不会**索取、读取、记录你的账号密码；脚本不碰任何输入框内容
- 不绕过验证码、不做签名逆向；只是把你本人登录后的会话 Cookie 取出来
- Cookie 只写入 .env，终端输出只显示掩码
- 浏览器资料保存在 .browser-profile/（同样被 gitignore），下次可复用登录态

用法:
    python login_browser.py                    # 依次登录四个平台
    python login_browser.py xianyu xiaohongshu # 只登录指定平台
    python login_browser.py --timeout 300      # 每个平台最多等 5 分钟
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.config import ENV_FILE  # noqa: E402

PROFILE_DIR = os.path.join(PROJECT_ROOT, ".browser-profile")

# 平台 -> 登录入口 / Cookie 域 / 登录后才会出现的 Cookie 名 / 环境变量名
PLATFORMS: Dict[str, dict] = {
    "xianyu": {
        "name": "闲鱼",
        "url": "https://www.goofish.com/",
        "hint": "点右上角「登录」→ 用手机闲鱼 App 扫码（或短信验证码）",
        "domains": ("goofish.com", "taobao.com", "tmall.com"),
        "login_cookies": ("unb", "_m_h5_tk"),
        "env": "XIANYU_COOKIE",
    },
    "xiaohongshu": {
        "name": "小红书",
        "url": "https://www.xiaohongshu.com/explore",
        "hint": "页面会自动弹出登录框 → 用小红书 App 扫码",
        "domains": ("xiaohongshu.com",),
        "login_cookies": ("web_session",),
        "env": "XIAOHONGSHU_COOKIE",
    },
    "douban": {
        "name": "豆瓣",
        "url": "https://accounts.douban.com/passport/login",
        "hint": "用手机豆瓣 App 扫码登录（也可用短信验证码）",
        "domains": ("douban.com", "doubanio.com"),
        "login_cookies": ("dbcl2",),
        "env": "DOUBAN_COOKIE",
    },
    "beike": {
        "name": "贝壳找房",
        "url": "https://sz.zu.ke.com/zufang",
        "hint": "点右上角「登录 / 注册」→ 用贝壳 App 扫码（贝壳列表页本身公开，登录主要用于降低验证码概率）",
        "domains": ("ke.com", "lianjia.com"),
        "login_cookies": ("lianjia_token", "ke_uid", "lianjia_uuid"),
        "env": "BEIKE_COOKIE",
    },
}

BANNER_ID = "__login_helper_banner"


def mask(value: str, head: int = 6, tail: int = 4) -> str:
    if not value:
        return "(空)"
    if len(value) <= head + tail:
        return f"({len(value)} 字符，已隐藏)"
    return f"{value[:head]}…{value[-tail:]}（{len(value)} 字符）"


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


async def inject_banner(page, text: str, color: str = "#00a3ca"):
    """在页面上浮一条提示，告诉用户该做什么（点不到也不影响原页面）"""
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
        pass  # 注入失败不影响登录本身


async def collect_cookies(context, domains) -> str:
    """把浏览器里的 Cookie 拼成请求头格式（只取该平台的域）"""
    cookies = await context.cookies()
    picked = [c for c in cookies
              if any(d in (c.get("domain") or "") for d in domains)]
    # 同名 Cookie 只保留一个（取路径最长的，通常最具体）
    best: Dict[str, dict] = {}
    for c in picked:
        name = c["name"]
        if name not in best or len(c.get("path") or "") > len(best[name].get("path") or ""):
            best[name] = c
    return "; ".join(f"{k}={v['value']}" for k, v in sorted(best.items()))


async def context_cookie_names(context) -> set:
    cookies = await context.cookies()
    return {c["name"] for c in cookies}


def login_evidence(context_cookie_names, platform: str) -> Optional[str]:
    """判断平台是否已下发登录态 Cookie —— 这是"登录成功"的主证据

    为什么不用接口探针当主判据：闲鱼的搜索接口、小红书的搜索接口都需要
    页面 JS 生成的签名参数（x-sign / x-s），**即使登录成功，直接调接口也会失败**。
    早先版本用接口探针判定，导致用户明明登录成功却被判为失败、Cookie 没被保存。
    正确做法：以"平台确实下发了只在登录后出现的 Cookie"为证据，
    接口能否直采作为单独的、如实说明的能力项。
    """
    info = PLATFORMS[platform]
    hits = [n for n in info["login_cookies"] if n in context_cookie_names]
    if not hits:
        return None
    return "、".join(hits)


async def probe_capability(platform: str, cookie: str) -> dict:
    """接口探针：只用于如实说明"能否直接采集"，不作为登录成功与否的判据"""
    from backend.crawlers.base import STATUS_OK
    from backend.crawlers.manager import CrawlerManager

    crawler_class = CrawlerManager.CRAWLERS.get(platform)
    if crawler_class is None:
        return {"ok": False, "status": "unknown", "message": "未注册的适配器"}
    crawler = crawler_class(cookie=cookie)
    try:
        health = await crawler.check_health()
        return {"ok": health.get("status") == STATUS_OK,
                "status": health.get("status"),
                "message": health.get("message", "")}
    except Exception as e:
        return {"ok": False, "status": "error", "message": f"{type(e).__name__}: {e}"}
    finally:
        try:
            await crawler.close()
        except Exception:
            pass


async def login_one(context, platform: str, timeout: int) -> bool:
    info = PLATFORMS[platform]
    page = await context.new_page()
    print(f"\n{'=' * 70}", flush=True)
    print(f"【{info['name']}】请在打开的浏览器窗口里完成登录", flush=True)
    print(f"  {info['hint']}", flush=True)
    print(f"  最多等待 {timeout // 60} 分钟，检测到登录态会立即保存并跳到下一个", flush=True)
    print(f"{'=' * 70}", flush=True)

    try:
        await page.goto(info["url"], wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        print(f"  ⚠️ 打开页面失败：{type(e).__name__}: {str(e)[:80]}", flush=True)

    try:
        await page.bring_to_front()
    except Exception:
        pass

    started = time.time()
    while time.time() - started < timeout:
        await inject_banner(
            page,
            f"登录助手：请在此窗口登录【{info['name']}】—— {info['hint']}",
        )

        names = await context_cookie_names(context)
        evidence = login_evidence(names, platform)
        if evidence:
            cookie = await collect_cookies(context, info["domains"])
            if cookie and len(cookie) > 30:
                write_env(info["env"], cookie)
                print(f"  ✅ 检测到登录态（依据：{evidence}），已写入 .env 的 {info['env']}"
                      f"（掩码 {mask(cookie)}）", flush=True)

                # 接口能力单独探一次，如实说明能否直接采集
                probe = await probe_capability(platform, cookie)
                if probe["ok"]:
                    print(f"  ✅ 接口探针：可直接采集", flush=True)
                else:
                    print(f"  ℹ️ 接口探针未通过（{probe['status']}）：{probe['message'][:80]}", flush=True)
                    print(f"     说明：{info['name']}的搜索接口还需要页面签名参数，"
                          f"登录态已保存，采集能力随后验证", flush=True)

                await inject_banner(page, f"✅ {info['name']} 登录成功，已保存！", "#52c41a")
                await page.wait_for_timeout(1500)
                return True

        await page.wait_for_timeout(2500)

    print(f"  ⏰ {info['name']} 等待超时，跳过", flush=True)
    print(f"     可稍后重试：python login_browser.py {platform}", flush=True)
    print(f"     或手工复制 Cookie：python import_cookie.py {platform}", flush=True)
    return False


async def adopt_existing() -> int:
    """接管浏览器资料里**已有的登录态**：不等待、不打开新页面，直接读取并保存

    适用场景：上一次登录成功了，但因为判定逻辑或浏览器被关掉而没保存下来。
    只要平台的登录 Cookie 还在资料里，就能直接取出来用。
    """
    from playwright.async_api import async_playwright

    saved = []
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            PROFILE_DIR, headless=True,
            viewport={"width": 1280, "height": 860})
        try:
            names = await context_cookie_names(context)
            print(f"浏览器资料中共有 {len(names)} 个 Cookie", flush=True)
            for platform in PLATFORMS:
                info = PLATFORMS[platform]
                evidence = login_evidence(names, platform)
                if not evidence:
                    print(f"  —  {info['name']:8} 无登录态", flush=True)
                    continue
                cookie = await collect_cookies(context, info["domains"])
                if not cookie or len(cookie) < 30:
                    print(f"  ⚠️  {info['name']:8} 有证据但取不到 Cookie", flush=True)
                    continue
                write_env(info["env"], cookie)
                saved.append(platform)
                print(f"  ✅ {info['name']:8} 已接管并写入 {info['env']}"
                      f"（依据：{evidence}；掩码 {mask(cookie)}）", flush=True)
        finally:
            await context.close()

    if saved:
        print(f"\n✅ 已接管：{'、'.join(PLATFORMS[p]['name'] for p in saved)}", flush=True)
        print("   下一步：python import_cookie.py --check 查看接口能力", flush=True)
    else:
        print("\n没有找到可接管的登录态", flush=True)
    return 0


async def main():
    parser = argparse.ArgumentParser(description="打开浏览器登录并自动保存 Cookie")
    parser.add_argument("platforms", nargs="*", choices=sorted(PLATFORMS),
                        help="要登录的平台，默认全部（按推荐顺序）")
    parser.add_argument("--timeout", type=int, default=420,
                        help="每个平台最长等待秒数（默认 420 = 7 分钟）")
    parser.add_argument("--adopt", action="store_true",
                        help="不等待登录，直接接管浏览器资料里已有的登录态")
    args = parser.parse_args()

    if args.adopt:
        return await adopt_existing()

    targets: List[str] = args.platforms or ["xianyu", "xiaohongshu", "douban", "beike"]

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ 未安装 playwright：pip install playwright && python -m playwright install chromium")
        return 1

    os.makedirs(PROFILE_DIR, exist_ok=True)

    print("=" * 70)
    print("登录助手")
    print("=" * 70)
    print("即将打开一个浏览器窗口。请在里面用**扫码 / 短信验证码**正常登录。")
    print("· 脚本不会读取你输入的任何内容，也不处理密码")
    print("· 登录成功后自动把 Cookie 写入 .env（只显示掩码）")
    print(f"· 依次处理：{'、'.join(PLATFORMS[p]['name'] for p in targets)}")
    print("=" * 70)

    saved = []
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 860},
            args=["--window-position=60,60"],
        )
        try:
            for platform in targets:
                ok = await login_one(context, platform, args.timeout)
                if ok:
                    saved.append(platform)
                else:
                    await context.pages[-1].close() if context.pages else None
        finally:
            await context.close()

    print("\n" + "=" * 70)
    if saved:
        print(f"✅ 已保存：{'、'.join(PLATFORMS[p]['name'] for p in saved)}")
        print("   查看状态：python import_cookie.py --status")
        print("   校验有效性：python import_cookie.py --check")
    else:
        print("⚠️ 本次没有保存任何 Cookie")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
