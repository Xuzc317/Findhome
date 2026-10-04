#!/usr/bin/env python3
"""
平台 Cookie 导入与校验

用途：把你在**自己浏览器**里正常登录后拿到的 Cookie 安全地写入 .env，
并在写入前用真实请求验证它是否有效——避免"填了但其实是失效的"。

安全约定（重要）：
- 本脚本**只接受 Cookie**，不索取、不处理账号密码；
- Cookie 只写入项目根目录 `.env`（已被 .gitignore 忽略），不写代码/文档/日志；
- 任何输出（终端、报错、校验结果）都只显示掩码，不打印 Cookie 原文。

用法:
    # 交互式导入（推荐，粘贴后立即校验）
    python import_cookie.py douban

    # 直接带上 Cookie（会出现在 shell 历史里，谨慎使用）
    python import_cookie.py douban --cookie "bid=xxx; dbcl2=yyy"

    # 校验当前 .env 里所有平台的 Cookie 是否仍然有效
    python import_cookie.py --check

    # 查看状态 / 清除某个平台
    python import_cookie.py --status
    python import_cookie.py douban --clear

浏览器获取步骤：
    1. 在自己的浏览器里正常登录该平台（可扫码/短信验证码）
    2. F12 → Network → 刷新页面 → 点任意请求 → Request Headers
    3. 复制整行 Cookie 的值（形如 key=value; key2=value2）
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Dict, Optional

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.config import ENV_FILE, get_settings, is_configured  # noqa: E402
from backend.crawlers.base import (  # noqa: E402
    STATUS_NEEDS_LOGIN,
    STATUS_OK,
    BaseCrawler,
)

# 平台 -> (环境变量名, 爬虫类, 说明)
PLATFORMS: Dict[str, dict] = {}


def _load_platforms():
    from backend.crawlers.beike import BeikeCrawler
    from backend.crawlers.douban import DoubanCrawler
    from backend.crawlers.xianyu import XianyuCrawler
    from backend.crawlers.xiaohongshu import XiaohongshuCrawler

    PLATFORMS.update({
        "douban": {
            "env": "DOUBAN_COOKIE",
            "cls": DoubanCrawler,
            "name": "豆瓣租房",
            "tip": "未登录时豆瓣容易触发风控中间页；带上登录 Cookie 后成功率明显提高",
        },
        "beike": {
            "env": "BEIKE_COOKIE",
            "cls": BeikeCrawler,
            "name": "贝壳找房",
            "tip": "列表页本身公开；Cookie 主要用于降低验证码触发概率",
        },
        "xianyu": {
            "env": "XIANYU_COOKIE",
            "cls": XianyuCrawler,
            "name": "闲鱼",
            "tip": "必需：未登录时搜索接口直接返回 RGV587_ERROR 并跳登录页",
        },
        "xiaohongshu": {
            "env": "XIAOHONGSHU_COOKIE",
            "cls": XiaohongshuCrawler,
            "name": "小红书",
            "tip": "必需：未登录时接口返回 code=-101「无登录信息」",
        },
    })


def mask(value: str, head: int = 6, tail: int = 4) -> str:
    """只显示掩码，绝不打印 Cookie 原文"""
    if not value:
        return "(空)"
    value = value.strip()
    if len(value) <= head + tail:
        return f"({len(value)} 字符，已隐藏)"
    return f"{value[:head]}…{value[-tail:]}（{len(value)} 字符）"


# ---------- .env 读写 ----------

def write_env(key: str, value: str) -> None:
    """写入/更新 .env 中的一项，保留其余内容与注释、保持文件权限不变"""
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

    out, replaced = [], False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
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
        os.chmod(ENV_FILE, 0o600)  # 仅本人可读写
    except OSError:
        pass


def clear_env(key: str) -> None:
    write_env(key, "")


# ---------- 校验 ----------

async def validate(platform: str, cookie: str) -> dict:
    """用真实请求校验 Cookie 是否有效

    直接复用各 Adapter 的 check_health()——它们做的是"真实请求 + 真实解析"，
    而不是只看 HTTP 200。返回 {"ok": bool, "status": str, "message": str}。
    """
    info = PLATFORMS[platform]
    crawler: BaseCrawler = info["cls"](cookie=cookie)
    try:
        if not getattr(crawler, "has_cookie", False):
            return {"ok": False, "status": STATUS_NEEDS_LOGIN,
                    "message": "Cookie 为空"}
        health = await crawler.check_health()
        status = health.get("status", "error")
        return {
            "ok": status == STATUS_OK,
            "status": status,
            "message": health.get("message", ""),
            "verified": health.get("verified", False),
        }
    except Exception as e:
        return {"ok": False, "status": "error",
                "message": f"{type(e).__name__}: {e}"}
    finally:
        try:
            await crawler.close()
        except Exception:
            pass


# ---------- 命令 ----------

def cmd_status() -> int:
    settings = get_settings()
    print("\n各平台 Cookie 状态（不显示内容）")
    print("=" * 72)
    for key, info in PLATFORMS.items():
        value = getattr(settings, key + "_cookie", "") or ""
        # is_configured 会把 your_xxx_here 这类占位符也算作未配置
        state = "✅ 已配置" if is_configured(value) else "—  未配置"
        print(f"  {info['name']:8} ({key:11}) {state}")
        if is_configured(value):
            print(f"      掩码: {mask(value)}")
        else:
            print(f"      获取: python import_cookie.py {key}")
    print("=" * 72)
    return 0


async def cmd_check() -> int:
    settings = get_settings()
    print("\n校验 .env 中已配置的 Cookie（真实请求）")
    print("=" * 72)
    checked = ok_count = 0
    for key, info in PLATFORMS.items():
        value = getattr(settings, key + "_cookie", "") or ""
        if not is_configured(value):
            print(f"  ⏭️  {info['name']:8} 未配置，跳过")
            continue
        checked += 1
        result = await validate(key, value)
        icon = "✅" if result["ok"] else "❌"
        ok_count += bool(result["ok"])
        print(f"  {icon} {info['name']:8} [{result['status']}] {result['message'][:80]}")
    print("=" * 72)
    print(f"结果: {ok_count}/{checked} 个已配置的 Cookie 校验通过")
    return 0 if checked == 0 or ok_count == checked else 2


async def cmd_import(platform: str, cookie: str, force: bool,
                     skip_validate: bool) -> int:
    info = PLATFORMS[platform]

    if not cookie.strip():
        print(f"\n请粘贴 {info['name']} 的 Cookie。")
        print(f"提示: {info['tip']}")
        print("（在浏览器登录后：F12 → Network → 任意请求 → Request Headers → 复制 Cookie 整行）")
        try:
            cookie = input("\nCookie> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return 1

    if not cookie.strip():
        print("❌ Cookie 为空，已取消")
        return 1

    print(f"\n待导入: {info['name']}  掩码 {mask(cookie)}")

    if skip_validate:
        print("⚠️  已跳过校验（--skip-validate），Cookie 可能无效")
    else:
        print("正在用真实请求校验……")
        result = await validate(platform, cookie)
        icon = "✅" if result["ok"] else "❌"
        print(f"  {icon} 状态 [{result['status']}] {result['message'][:120]}")

        if not result["ok"] and not force:
            print("\n未写入 .env。可能原因：")
            print("  · Cookie 复制不完整（要复制整行，而不是单个字段）")
            print("  · 浏览器里其实没有登录成功，或登录态已过期")
            print("  · 平台要求额外的签名参数（闲鱼/小红书除 Cookie 外还需 x-sign/x-s）")
            print("\n如确认要强行写入，可加 --force")
            return 2

    write_env(info["env"], cookie.strip())
    print(f"\n✅ 已写入 {ENV_FILE} 的 {info['env']}（该文件已被 .gitignore 忽略）")
    print("   重启后端后生效，或执行 python crawl.py health 看状态变化")
    return 0


def main() -> int:
    _load_platforms()

    parser = argparse.ArgumentParser(
        description="平台 Cookie 导入与校验（只接受本人浏览器 Cookie，不处理密码）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("platform", nargs="?", choices=sorted(PLATFORMS),
                        help="平台名")
    parser.add_argument("--cookie", default="", help="直接提供 Cookie（会进 shell 历史，谨慎）")
    parser.add_argument("--check", action="store_true", help="校验 .env 中已配置的 Cookie")
    parser.add_argument("--status", action="store_true", help="查看各平台配置状态")
    parser.add_argument("--clear", action="store_true", help="清除该平台的 Cookie")
    parser.add_argument("--force", action="store_true", help="校验失败也写入")
    parser.add_argument("--skip-validate", action="store_true", help="跳过校验直接写入")
    args = parser.parse_args()

    if args.status:
        return cmd_status()
    if args.check:
        return asyncio.run(cmd_check())

    if not args.platform:
        parser.print_help()
        return 1

    if args.clear:
        info = PLATFORMS[args.platform]
        clear_env(info["env"])
        print(f"🗑️  已清除 {info['name']} 的 Cookie（{info['env']}）")
        return 0

    return asyncio.run(cmd_import(args.platform, args.cookie,
                                  args.force, args.skip_validate))


if __name__ == "__main__":
    sys.exit(main())
