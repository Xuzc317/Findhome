#!/usr/bin/env python3
"""
解析器离线测试

用**真实页面结构的复刻快照**验证解析逻辑，不需要联网、不会触发平台风控。
这样平台风控期间也能确认解析代码是否正确。

运行:
    python tests/test_parsers.py
"""

import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.crawlers.base import (  # noqa: E402
    detect_block,
    extract_price,
    parse_relative_time,
)
from backend.crawlers.beike import BeikeCrawler  # noqa: E402
from backend.crawlers.douban import DoubanCrawler  # noqa: E402

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


# ==================== 贝壳列表页快照 ====================
# 结构复刻自 2026-10-04 实际抓取的 https://sz.zu.ke.com/zufang 页面
BEIKE_LIST_HTML = """
<html><head><title>深圳租房信息_深圳出租房源|房屋出租价格【深圳贝壳租房】</title></head>
<body>
<div class="content__list">
  <div class="content__list--item" data-house_code="SZ2216761791667503104">
    <a class="content__list--item--aside" href="/zufang/SZ2216761791667503104.html">
      <img class="lazyload" data-src="https://ke-image.ljcdn.com/110000-inspection/pc1_abc.jpg!m_fill,w_250,h_182">
    </a>
    <div class="content__list--item--main">
      <p class="content__list--item--title">
        <a class="twoline" href="/zufang/SZ2216761791667503104.html">整租·麒麟花园B区 3室1厅 南</a>
      </p>
      <p class="content__list--item--des">
        <a href="/zufang/nanshanqu/">南山区</a>-<a href="/zufang/nantou/">南头</a>-<a href="/zufang/xiaoqu/">麒麟花园B区</a>/89.00㎡/南/3室1厅1卫/中楼层（20层）
      </p>
      <span class="content__list--item-price"><em>8600</em>元/月</span>
      <span class="content__list--item--bottom oneline">
        <i class="content__item__tag--is_subway_house">近地铁</i>
        <i class="content__item__tag--decoration">精装</i>
        <i class="content__item__tag--is_new">新上</i>
      </span>
      <span class="content__list--item--time oneline">3天前维护</span>
    </div>
  </div>
  <div class="content__list--item" data-house_code="SZ2206834180233363456">
    <a class="content__list--item--aside" href="/zufang/SZ2206834180233363456.html">
      <img class="lazyload" data-src="https://s1.ljcdn.com/matrix_pc/dist/pc/src/resource/default/250-182.png">
    </a>
    <div class="content__list--item--main">
      <p class="content__list--item--title">
        <a class="twoline" href="/zufang/SZ2206834180233363456.html">合租·桑泰龙樾 4室2厅 南/北</a>
      </p>
      <p class="content__list--item--des">
        <a href="/zufang/longgangqu/">龙岗区</a>-<a href="/zufang/shuanglong/">龙岗双龙</a>-<a href="/zufang/x/">桑泰·龙樾</a>/96.00㎡/南 北/4室2厅1卫/高楼层（33层）
      </p>
      <span class="content__list--item-price"><em>4,000</em>元/月</span>
      <span class="content__list--item--time oneline">今天维护</span>
    </div>
  </div>
</div>
</body></html>
"""

BEIKE_CAPTCHA_HTML = """
<html><head><title>CAPTCHA</title></head>
<body><div class="captcha">请完成安全验证</div></body></html>
"""

BEIKE_LOGIN_HTML = """
<html><head><title>登录</title></head>
<body><div>请登录后继续</div></body></html>
"""

# ==================== 豆瓣小组列表页快照 ====================
# 结构复刻自 2026-10-04 实际抓取的 https://www.douban.com/group/26926/discussion
DOUBAN_LIST_HTML = """
<html><head><title>北京租房小组</title></head>
<body>
<table class="olt">
  <tr><th>标题</th><th>作者</th><th>回应</th><th>最后回应</th></tr>
  <tr>
    <td class="title"><a href="https://www.douban.com/group/topic/501579582/" title="房主直租 近16号线西北旺站 北向次卧 2800元/月">房主直租 近16号线西北旺站…</a></td>
    <td><a href="https://www.douban.com/people/aaa/">王白石</a></td>
    <td class="r-count">12</td>
    <td class="time">10-04 05:59</td>
  </tr>
  <tr>
    <td class="title"><a href="https://www.douban.com/group/topic/501566542/" title="北二环一居室出租 近师大北邮 整租 6500">北二环一居室出租</a></td>
    <td><a href="https://www.douban.com/people/bbb/">老宋</a></td>
    <td class="r-count">3</td>
    <td class="time">昨天 23:46</td>
  </tr>
  <tr>
    <td class="title"><a href="https://www.douban.com/group/topic/501560927/" title="【置顶】本组规则请先阅读">【置顶】本组规则</a></td>
    <td><a href="https://www.douban.com/people/ccc/">管理员</a></td>
    <td class="r-count">0</td>
    <td class="time">2024-01-15</td>
  </tr>
</table>
</body></html>
"""

DOUBAN_BLOCK_HTML = """
<html><head><title>豆瓣</title></head>
<body><div>请点击下方按钮继续浏览或 登录 使用豆瓣</div>
<button>点我继续浏览</button></body></html>
"""


def test_price():
    print("\n【租金提取】")
    check("带「元/月」", extract_price("整租 3500元/月 近地铁") == 3500)
    check("带「/月」", extract_price("合租主卧 2500/月 押一付三") == 2500)
    check("带「月租」", extract_price("月租3000 精装修") == 3000)
    check("带「k」", extract_price("3.5k 一室一厅") == 3500)
    check("手机号不当租金", extract_price("看房13126812883") is None)
    check("手机号+租金只取租金", extract_price("租金5000 电话13900139000") == 5000)
    check("年份不当租金", extract_price("2024年新装修 一居室") is None)
    check("长数字不当租金", extract_price("合同编号 500656129 一居室") is None)
    check("无价格语境时兜底裸数字", extract_price("两室一厅 8000") == 8000)


def test_relative_time():
    print("\n【相对时间解析】")
    now = datetime(2026, 10, 4, 12, 0, 0)
    check("3天前", parse_relative_time("3天前维护", now) == datetime(2026, 10, 1, 12, 0))
    check("1天前", parse_relative_time("1天前维护", now) == datetime(2026, 10, 3, 12, 0))
    check("今天", parse_relative_time("今天维护", now) == datetime(2026, 10, 4, 0, 0))
    check("昨天", parse_relative_time("昨天维护", now) == datetime(2026, 10, 3, 0, 0))
    check("无时间表述返回 None", parse_relative_time("暂无信息", now) is None)


def test_block_detection():
    print("\n【拦截页识别】")
    check("豆瓣风控中间页", detect_block(DOUBAN_BLOCK_HTML) is not None)
    check("贝壳验证码页", detect_block(BEIKE_CAPTCHA_HTML) is not None)
    check("正常列表页不误判", detect_block(BEIKE_LIST_HTML) is None)
    check("正常小组页不误判", detect_block(DOUBAN_LIST_HTML) is None)
    # 贝壳正常页面内联 JS 里会出现 captchaDomain，不能因此误判
    check("内联JS含captchaDomain不误判",
          detect_block('<html><head><title>深圳租房</title></head><body>'
                       '<script>window.x={captchaDomain:"https://captcha.ke.com"}</script>'
                       '<div class="content__list--item">ok</div></body></html>') is None)


def test_beike_parser():
    print("\n【贝壳列表解析】")
    crawler = BeikeCrawler(cookie="")
    houses, reason = crawler._parse_list(BEIKE_LIST_HTML, "深圳")
    check("解析出 2 条", len(houses) == 2, f"实际 {len(houses)}")
    check("无失败原因", reason is None, str(reason))
    if not houses:
        return

    h = houses[0]
    check("标题正确", h.title == "整租·麒麟花园B区 3室1厅 南", h.title)
    check("价格正确", h.price == 8600, str(h.price))
    check("房源编号（source_id）", h.source_id == "SZ2216761791667503104", str(h.source_id))
    check("行政区", h.district == "南山区", str(h.district))
    check("商圈", h.area == "南头", str(h.area))
    check("小区", h.community == "麒麟花园B区", str(h.community))
    check("面积", h.area_size == 89.0, str(h.area_size))
    check("朝向", h.orientation == "南", str(h.orientation))
    check("户型", h.room_type == "3室1厅1卫", str(h.room_type))
    check("标签提取（含真实标签）", "近地铁" in h.tags and "精装" in h.tags, str(h.tags))
    check("最近维护时间", h.last_active_time is not None, str(h.last_active_time))
    check("发布时间留空（不猜测）", h.publish_time is None, str(h.publish_time))
    check("出租类型=整租", h.rent_type == 3, str(h.rent_type))
    check("房源链接为绝对地址",
          h.source_url == "https://sz.zu.ke.com/zufang/SZ2216761791667503104.html", h.source_url)
    check("占位图被过滤", all("default/250-182" not in img for img in h.images), str(h.images))

    h2 = houses[1]
    check("合租类型识别", h2.rent_type == 1, str(h2.rent_type))
    check("带千分位价格", h2.price == 4000, str(h2.price))
    check("南北朝向", h2.orientation == "南 北", str(h2.orientation))
    check("今天维护可解析", h2.last_active_time is not None, str(h2.last_active_time))


# 布局变体：描述里 "/" 两侧带空格，且主正则不匹配时走兜底
BEIKE_VARIANT_HTML = """
<html><head><title>深圳租房</title></head><body>
<div class="content__list">
  <div class="content__list--item" data-house_code="SZ999">
    <a class="content__list--item--aside" href="/zufang/SZ999.html"><img data-src="https://img/a.jpg"></a>
    <div class="content__list--item--main">
      <p class="content__list--item--title"><a class="twoline" href="/zufang/SZ999.html">整租·桃源村二期 3室2厅 南</a></p>
      <p class="content__list--item--des">南山区 - 西丽 - 桃源村二期 / 93.22㎡ / 南 / 3室2厅1卫 / 高楼层 （20层）</p>
      <span class="content__list--item-price"><em>6195</em>元/月</span>
      <span class="content__list--item--time">4天前维护</span>
    </div>
  </div>
</div></body></html>
"""


def test_beike_variant():
    print("\n【贝壳布局变体兜底】")
    crawler = BeikeCrawler(cookie="")
    houses, reason = crawler._parse_list(BEIKE_VARIANT_HTML, "深圳")
    check("仍能解析出房源", len(houses) == 1, f"实际 {len(houses)}")
    if not houses:
        return
    h = houses[0]
    check("面积兜底", h.area_size == 93.22, str(h.area_size))
    check("户型兜底", h.room_type == "3室2厅1卫", str(h.room_type))
    check("行政区", h.district == "南山区", str(h.district))
    check("商圈", h.area == "西丽", str(h.area))
    check("维护时间", h.last_active_time is not None, str(h.last_active_time))


def test_beike_block_paths():
    print("\n【贝壳异常页面】")
    crawler = BeikeCrawler(cookie="")
    houses, reason = crawler._parse_list(BEIKE_CAPTCHA_HTML, "深圳")
    check("验证码页 → 空结果 + 原因", houses == [] and reason is not None, str(reason))
    check("状态标记为 blocked", crawler.last_status == "blocked", crawler.last_status)

    crawler2 = BeikeCrawler(cookie="")
    houses, reason = crawler2._parse_list(BEIKE_LOGIN_HTML, "深圳")
    check("登录页 → needs_login", crawler2.last_status == "needs_login", crawler2.last_status)


def test_douban_parser():
    print("\n【豆瓣列表解析】")
    import asyncio

    crawler = DoubanCrawler(cookie="")

    async def run():
        # 直接复用解析逻辑：伪造 response
        class FakeResp:
            status_code = 200
            text = DOUBAN_LIST_HTML

        original_get = crawler.get

        async def fake_get(url, **kwargs):
            return FakeResp()

        crawler.get = fake_get
        try:
            return await crawler._fetch_group("26926", "北京", "", 1)
        finally:
            crawler.get = original_get

    houses, reason = asyncio.run(run())
    check("解析出 2 条（置顶被跳过）", len(houses) == 2, f"实际 {len(houses)}")
    check("无失败原因", reason is None, str(reason))
    if not houses:
        return

    h = houses[0]
    check("标题取 title 属性全文", h.title.startswith("房主直租 近16号线西北旺站"), h.title[:26])
    check("帖子ID", h.source_id == "501579582", str(h.source_id))
    check("作者（不是时间）", h.publisher == "王白石", str(h.publisher))
    check("时间解析正确", h.publish_time is not None and h.publish_time.hour == 5
          and h.publish_time.minute == 59, str(h.publish_time))
    check("租金提取", h.price == 2800, str(h.price))
    check("出租类型=合租", h.rent_type == 1, str(h.rent_type))
    check("记录时间语义", "最后回应时间" in (h.raw_data or {}).get("time_semantics", ""),
          str((h.raw_data or {}).get("time_semantics")))

    h2 = houses[1]
    check("昨天时间解析", h2.publish_time is not None, str(h2.publish_time))
    check("整租识别", h2.rent_type == 3, str(h2.rent_type))
    check("裸数字租金兜底", h2.price == 6500, str(h2.price))


def test_normalize():
    print("\n【标准化：缺失字段不猜测】")
    from backend.crawlers.base import RawHouse

    raw = RawHouse(source="beike", title="测试房源", source_url="https://x/1")
    data = BeikeCrawler.normalize(raw)
    for field in ["price", "publish_time", "last_active_time", "longitude", "latitude",
                  "district", "area_size", "description"]:
        check(f"{field} 保持 None", data.get(field) is None, str(data.get(field)))
    check("source 保留", data["source"] == "beike")
    check("images 默认空数组字符串", data["images"] == "[]", data["images"])


def main():
    print("=" * 66)
    print("解析器离线测试（无需联网，不会触发平台风控）")
    print("=" * 66)
    test_price()
    test_relative_time()
    test_block_detection()
    test_beike_parser()
    test_beike_variant()
    test_beike_block_paths()
    test_douban_parser()
    test_normalize()
    print("\n" + "=" * 66)
    print(f"结果: ✅ 通过 {PASSED} | ❌ 失败 {FAILED}")
    print("=" * 66)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
