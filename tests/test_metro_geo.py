#!/usr/bin/env python3
"""
地铁 / 坐标 / 房型 / 定位 的离线测试

不需要联网（地铁静态数据除外），不消耗高德与大模型配额。

运行:
    python tests/test_metro_geo.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.services.amap import haversine_meters  # noqa: E402
from backend.services.coords import (  # noqa: E402
    convert_if_wgs84,
    gcj02_to_wgs84,
    wgs84_to_gcj02,
)
from backend.services.geolocate import (  # noqa: E402
    extract_candidates,
    normalize_station_name,
)
from backend.services.layout import parse_layout  # noqa: E402
from backend.services.metro import (  # noqa: E402
    _clean_station_name,
    _parse_lines_from_address,
    station_match_key,
    static_path,
)

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


def test_coords():
    print("\n【坐标系转换 WGS-84 ↔ GCJ-02】")
    lng, lat = wgs84_to_gcj02(114.0579, 22.5431)  # 深圳市民中心
    offset = haversine_meters(114.0579, 22.5431, lng, lat)
    check("深圳地区偏移量在合理区间(300~900m)", 300 < offset < 900, f"{offset}m")
    check("转换后坐标在中国境内", 113 < lng < 115 and 22 < lat < 23,
          f"({lng:.5f},{lat:.5f})")

    # 往返转换应回到原点附近
    back_lng, back_lat = gcj02_to_wgs84(lng, lat)
    round_trip = haversine_meters(114.0579, 22.5431, back_lng, back_lat)
    check("往返转换误差 < 5m", round_trip < 5, f"{round_trip}m")

    # 境外坐标不做偏移
    out_lng, out_lat = wgs84_to_gcj02(139.6917, 35.6895)  # 东京
    check("境外坐标不偏移", (out_lng, out_lat) == (139.6917, 35.6895))

    # 按来源决定是否转换
    _, _, note = convert_if_wgs84(114.05, 22.54, "wikidata")
    check("wikidata 来源会被转换", "已转换" in note, note)
    same_lng, _, note2 = convert_if_wgs84(114.05, 22.54, "amap")
    check("amap 来源原样保留", same_lng == 114.05 and "无需转换" in note2, note2)


def test_layout():
    print("\n【房型解析（按卧室数归档）】")
    cases = [
        ("整租·泓瀚苑 3室2厅 南", "3b1l", 3),
        ("整租·麒麟花园B区 3室1厅 南", "3b1l", 3),
        ("两室一厅 精装修", "2b1l", 2),
        ("2室1厅1卫 南向", "2b1l", 2),
        ("一居室整租 近地铁", "1b1l", 1),
        ("1室1厅 拎包入住", "1b1l", 1),
        ("合租 主卧带阳台", "studio", 0),
        ("单间出租 押一付一", "studio", 0),
        ("开间 精装 近地铁", "studio", 0),
        ("4室2厅2卫 大平层", "4b+", 4),
    ]
    for text, expect_key, expect_bed in cases:
        result = parse_layout(text)
        check(f"{text[:22]:24} → {expect_key}",
              result.layout_key == expect_key and result.bedrooms == expect_bed,
              f"实际 {result.layout_key}/bedrooms={result.bedrooms} 依据={result.evidence}")

    # 关键回归：出现"主卧"但明确写了"两室一厅"时，必须按卧室数解析
    mixed = parse_layout("转租 两室一厅 主卧带阳台 近3号线布吉站")
    check("“两室一厅 + 主卧”按卧室数解析（大模型在此会答错）",
          mixed.layout_key == "2b1l", f"实际 {mixed.layout_key} 依据={mixed.evidence}")

    # 解析不出就留空，不猜
    empty = parse_layout("好房出租 价格面议")
    check("无房型信息时留空", empty.layout_key is None, str(empty.layout_key))

    # 出租类型兜底置信度更低
    fallback = parse_layout("", rent_type=1)
    check("仅凭合租类型兜底且置信度低",
          fallback.layout_key == "studio" and fallback.confidence <= 45,
          f"{fallback.layout_key}/{fallback.confidence}")


def test_station_names():
    print("\n【站名规整】")
    cases = [
        ("5号线坂田站", "坂田站"),
        ("地铁1号线深大", "深大站"),
        ("三号线布吉站", "布吉站"),
        ("2号线(8号线)世界之窗", "世界之窗站"),
        ("坂田", "坂田站"),
        ("西北旺站", "西北旺站"),
    ]
    for raw, expect in cases:
        got = normalize_station_name(raw)
        check(f"{raw!r} → {expect!r}", got == expect, f"实际 {got!r}")

    check("高德 POI 名去后缀", _clean_station_name("深大(地铁站)") == "深大")
    check("跨来源站名匹配键一致",
          station_match_key("深圳北站") == station_match_key("深圳北"),
          f"{station_match_key('深圳北站')} vs {station_match_key('深圳北')}")


def test_metro_line_parsing():
    print("\n【高德 POI 线路解析】")
    check("多线路分号分隔",
          _parse_lines_from_address("11号线/机场线;1号线/罗宝线;7号线/西丽线")
          == ["11号线", "1号线", "7号线"])
    check("贯通运营的括号线路也要登记（2/8号线）",
          _parse_lines_from_address("2号线(8号线)") == ["8号线", "2号线"],
          str(_parse_lines_from_address("2号线(8号线)")))
    check("空地址返回空列表", _parse_lines_from_address("") == [])


def test_static_dataset():
    print("\n【地铁静态数据】")
    path = static_path("深圳")
    check("能找到静态数据文件", os.path.exists(path), os.path.basename(path))
    if not os.path.exists(path):
        return

    import json
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    lines = data.get("lines") or []
    check("线路数 >= 17", len(lines) >= 17, f"{len(lines)} 条")

    total = 0
    missing_coord = 0
    names = set()
    for line in lines:
        for station in line.get("stations") or []:
            total += 1
            names.add(station.get("name"))
            if station.get("lng") is None or station.get("lat") is None:
                missing_coord += 1

    check("站点条目数 >= 400", total >= 400, f"{total} 条")
    check("去重站名 >= 340", len(names) >= 340, f"{len(names)} 个")
    check("坐标缺失数 == 0", missing_coord == 0, f"缺失 {missing_coord}")

    # 坐标必须落在深圳范围内（防止 WGS/GCJ 搞反或数据错位）
    out_of_range = 0
    for line in lines:
        for station in line.get("stations") or []:
            lng, lat = station.get("lng"), station.get("lat")
            if lng is None:
                continue
            if not (113.6 < lng < 114.7 and 22.3 < lat < 22.9):
                out_of_range += 1
    check("所有坐标落在深圳范围内", out_of_range == 0, f"越界 {out_of_range}")


def test_candidate_extraction():
    print("\n【位置候选抽取】")

    class FakeHouse:
        def __init__(self, **kw):
            self.title = kw.get("title")
            self.description = kw.get("description")
            self.tags = kw.get("tags")
            self.community = kw.get("community")
            self.address = kw.get("address")
            self.area = kw.get("area")
            self.district = kw.get("district")

    house = FakeHouse(
        title="整租·泓瀚苑 3室2厅 南",
        description="龙岗区-坂田-泓瀚苑 近5号线坂田站 步行8分钟 精装",
        community="泓瀚苑", district="龙岗区", area="坂田",
    )
    candidates = extract_candidates(house)
    check("抽取出候选", len(candidates) > 0, f"{len(candidates)} 个")
    kinds = {c.kind for c in candidates}
    check("包含小区候选", "community" in kinds, str(kinds))
    check("包含地铁站候选", "station" in kinds, str(kinds))
    check("小区候选置信度高于地铁站候选",
          max((c.confidence for c in candidates if c.kind == "community"), default=0)
          > max((c.confidence for c in candidates if c.kind == "station"), default=0),
          "")

    # 无任何位置信息时不应硬造候选
    bare = FakeHouse(title="好房出租", description="价格面议")
    check("无位置信息时不产生候选", len(extract_candidates(bare)) == 0,
          f"{len(extract_candidates(bare))} 个")


def main():
    print("=" * 66)
    print("地铁 / 坐标 / 房型 / 定位 离线测试")
    print("=" * 66)
    test_coords()
    test_layout()
    test_station_names()
    test_metro_line_parsing()
    test_static_dataset()
    test_candidate_extraction()
    print("\n" + "=" * 66)
    print(f"结果: ✅ 通过 {PASSED} | ❌ 失败 {FAILED}")
    print("=" * 66)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
