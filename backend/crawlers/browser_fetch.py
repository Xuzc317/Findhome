"""基于真实浏览器的搜索采集

**为什么需要它**：闲鱼、小红书这类平台的搜索接口要求页面 JS 生成的签名参数
（x-sign / x-s）。本项目不做签名逆向（那是绕过访问控制），
但可以用**真实浏览器按正常用户的方式打开搜索页**——页面自己的 JS 会完成签名，
我们只读取渲染出来的结果。这与手工浏览没有区别，也不触碰任何反爬机制。

设计要点：
- 复用 `.browser-profile/` 里的登录态（由 login_browser.py 建立），
  已登录时结果更全；未登录也能拿到首页结果
- 每个查询之间加礼貌间隔，不并发轰炸
- 只提取页面上**已经渲染出来**的内容，不注入脚本去调接口
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), ".browser-profile")

DEFAULT_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


@dataclass
class BrowserCard:
    """页面上抓到的原始卡片"""
    item_id: str
    title: str
    price_text: str
    url: str
    raw_text: str
    query: str
    image: str = ""


class BrowserSession:
    """一个可复用的浏览器会话（整批查询共用一个，避免反复启动）"""

    def __init__(self, profile_dir: str = PROFILE_DIR, headless: bool = True,
                 locale: str = "zh-CN", cdp_port: int | None = None):
        self.profile_dir = profile_dir
        self.headless = headless
        self.locale = locale
        self.cdp_port = cdp_port          # 指定则接管常驻浏览器，否则自己启动
        self._playwright = None
        self._owns_browser = True
        self.browser = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        from playwright.async_api import async_playwright

        os.makedirs(self.profile_dir, exist_ok=True)
        self._playwright = await async_playwright().start()

        if self.cdp_port:
            # 接管 browser_daemon.py 常驻的那个已登录浏览器
            # （会话级 Cookie 只在那个进程里有效，自己再开一个会丢登录态）
            self.browser = await self._playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{self.cdp_port}")
            if not self.browser.contexts:
                raise RuntimeError("调试端口已连接，但拿不到浏览器上下文")
            self.context = self.browser.contexts[0]
            self.page = await self.context.new_page()
            self._owns_browser = False
        else:
            self.context = await self._playwright.chromium.launch_persistent_context(
                self.profile_dir,
                headless=self.headless,
                viewport={"width": 1440, "height": 1000},
                user_agent=DEFAULT_UA,
                locale=self.locale,
            )
            self.page = await self.context.new_page()
            self._owns_browser = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """接管模式只关自己开的标签页，绝不关掉常驻浏览器（否则登录态就没了）"""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except Exception:
            pass
        try:
            if self._owns_browser and self.context:
                await self.context.close()
        finally:
            if self._playwright:
                await self._playwright.stop()
        return False

    async def close_login_popup(self) -> bool:
        """关闭可能弹出的登录框（不登录也能看首页结果，弹窗会挡住滚动）"""
        selectors = [
            'div[class*="login"] [class*="close"]',
            'div[class*="loginDialog"] svg',
            'div[class*="banner"] [class*="close"]',
            'button[aria-label="Close"]',
        ]
        for sel in selectors:
            try:
                el = self.page.locator(sel).first
                if await el.count():
                    await el.click(timeout=1200)
                    await self.page.wait_for_timeout(500)
                    return True
            except Exception:
                continue
        return False

    async def scrape_cards(self, url: str, item_selector: str,
                           wait_ms: int = 8000, scroll_times: int = 2,
                           query: str = "") -> List[dict]:
        """打开页面 → 等结果渲染 → 抓取卡片（含可选滚动加载）"""
        await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await self.page.wait_for_timeout(wait_ms)

        if await self.page.locator(item_selector).count() == 0:
            await self.close_login_popup()
            await self.page.wait_for_timeout(2500)

        for _ in range(scroll_times):
            if await self.page.locator(item_selector).count() > 0:
                break
            try:
                await self.page.mouse.wheel(0, 1400)
            except Exception:
                pass
            await self.page.wait_for_timeout(2500)

        cards = await self.page.eval_on_selector_all(
            item_selector,
            """els => els.map(e => {
                const href = e.getAttribute('href') || '';
                const txt = (e.innerText || '').replace(/\\s+/g, ' ').trim();
                // 图片：卡片内第一张有实际地址的 img（懒加载常用 data-src）
                const imgs = Array.from(e.querySelectorAll('img'));
                let img = '';
                for (const im of imgs) {
                    const cand = im.getAttribute('src') || im.getAttribute('data-src')
                        || im.getAttribute('data-lazy-src') || '';
                    if (cand && !cand.startsWith('data:')) {
                        // 去掉缩放后缀，取原图（各站规则不同，取到就用）
                        img = cand.startsWith('//') ? 'https:' + cand : cand;
                        break;
                    }
                }
                if (!img) {
                    const bg = getComputedStyle(e).backgroundImage || '';
                    const m = bg.match(/url\\(["']?([^"')]+)["']?\\)/);
                    if (m && !m[1].startsWith('data:')) img = m[1];
                }
                return {href, txt, img};
            }).filter(x => x.txt.length > 4)""",
        )
        for card in cards:
            card["query"] = query
        return cards


# ---------- 闲鱼 ----------

GOOFISH_ITEM_RE = re.compile(r"item\?id=(\d+)")
PRICE_RE = re.compile(r"[¥￥]\s*([\d,]+(?:\.\d+)?)")


def parse_goofish_cards(cards: List[dict], query: str) -> List[BrowserCard]:
    """把闲鱼卡片文本解析成结构化条目"""
    results: List[BrowserCard] = []
    seen = set()
    for card in cards:
        href = card.get("href") or ""
        match = GOOFISH_ITEM_RE.search(href)
        if not match:
            continue
        item_id = match.group(1)
        if item_id in seen:
            continue
        seen.add(item_id)

        text = card.get("txt") or ""
        price_match = PRICE_RE.search(text)
        # 标题 = 去掉价格片段后的前半段
        title = PRICE_RE.split(text)[0].strip(" -·|")
        title = re.sub(r"\s+", " ", title)[:200]
        if not title:
            continue

        results.append(BrowserCard(
            item_id=item_id,
            title=title,
            price_text=price_match.group(1) if price_match else "",
            url=f"https://www.goofish.com/item?id={item_id}",
            raw_text=text[:500],
            query=query,
            image=(card.get("img") or "").strip(),
        ))
    return results


async def search_goofish(session: BrowserSession, query: str,
                         wait_ms: int = 8000) -> List[BrowserCard]:
    """在闲鱼搜索一个关键词，返回卡片列表"""
    from urllib.parse import quote

    url = f"https://www.goofish.com/search?q={quote(query)}"
    cards = await session.scrape_cards(
        url, 'a[href*="item?id="]', wait_ms=wait_ms, query=query)
    return parse_goofish_cards(cards, query)


# ---------- 小红书 ----------

XHS_NOTE_RE = re.compile(r"/explore/([0-9a-f]{16,})")

# 明显不是"出租房源"的笔记：求租、吐槽、讨论
XHS_NOT_LISTING = re.compile(
    r"^(求租|寻租|找房|求推荐|想租)|求租|寻找房源|有没有.*(转租|出租)的吗|"
    r"真的很乱|吐槽|避雷|攻略|注意|小心|骗局|经验"
)
XHS_IS_LISTING = re.compile(r"出租|转租|直租|招租|房东|房源|押一付一|拎包入住|可短租")


async def search_xiaohongshu(session: "BrowserSession", query: str,
                             wait_ms: int = 9000) -> List[dict]:
    """在小红书搜索一个关键词，返回笔记卡片（标题 / 链接 / 作者 / 点赞）"""
    from urllib.parse import quote

    url = (f"https://www.xiaohongshu.com/search_result"
           f"?keyword={quote(query)}&source=web_explore_feed")
    await session.page.goto(url, wait_until="domcontentloaded", timeout=45000)
    await session.page.wait_for_timeout(wait_ms)

    if await session.page.locator('section[class*="note"]').count() == 0:
        # 可能是登录框遮住了，关掉再等
        await session.close_login_popup()
        await session.page.wait_for_timeout(3000)

    cards = await session.page.evaluate(
        r"""() => {
            const secs = Array.from(document.querySelectorAll('section[class*="note"]'));
            return secs.map(sec => {
                const a = sec.querySelector('a[href*="/explore/"]');
                const titleEl = sec.querySelector('[class*="title"]');
                const authorEl = sec.querySelector('[class*="author"], [class*="name"]');
                const im = sec.querySelector('img');
                let img = '';
                if (im) {
                    const cand = im.getAttribute('src') || im.getAttribute('data-src') || '';
                    if (cand && !cand.startsWith('data:')) img = cand.startsWith('//') ? 'https:' + cand : cand;
                }
                return {
                    href: a ? a.getAttribute('href') : '',
                    title: titleEl ? (titleEl.innerText || '').trim() : '',
                    author: authorEl ? (authorEl.innerText || '').replace(/\s+/g,' ').trim() : '',
                    text: (sec.innerText || '').replace(/\s+/g,' ').trim().slice(0, 200),
                    img: img,
                };
            }).filter(x => x.href && x.title);
        }"""
    )
    for card in cards:
        card["query"] = query
    return cards


def xhs_is_listing(title: str, text: str = "") -> bool:
    """判断一条小红书笔记是不是"出租房源"（排除求租、吐槽、攻略）"""
    blob = f"{title} {text}".strip()
    if not blob:
        return False
    if XHS_NOT_LISTING.search(title):
        return False
    return bool(XHS_IS_LISTING.search(blob))
