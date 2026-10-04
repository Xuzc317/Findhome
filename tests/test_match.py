#!/usr/bin/env python3
"""
条件识别 与 需求匹配 的离线测试

不联网：距离预筛与条件识别都是纯计算；步行阶段用假的 AmapClient 替代。

运行:
    python tests/test_match.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.models import Base, House, MetroLine, MetroLineStation, MetroStation  # noqa: E402
from backend.services.condition import analyze_condition, condition_summary  # noqa: E402
from backend.services.match import Profile, match  # noqa: E402

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


def test_elevator():
    print("\n【电梯识别：事实与推断必须分开】")
    r = analyze_condition("合租 主卧 电梯房 近地铁")
    check("明确写电梯 → True", r.elevator is True, f"依据={r.elevator_evidence}")

    # 关键回归：'无电梯' 含 '电梯' 两字，必须先匹配否定式
    r = analyze_condition("楼梯房 无电梯 6楼")
    check("'无电梯' 不被误判为有电梯", r.elevator is False, f"依据={r.elevator_evidence}")

    r = analyze_condition("步梯房 采光好")
    check("'步梯房' → False", r.elevator is False, f"依据={r.elevator_evidence}")

    r = analyze_condition("单间出租 采光好", floor_text="高楼层（33层）")
    check("未标注电梯 → None（不猜）", r.elevator is None)
    check("高楼层给出推断提示", r.elevator_hint is not None and "33" in r.elevator_hint,
          str(r.elevator_hint))

    r = analyze_condition("单间出租", floor_text="低楼层（6层）")
    check("低楼层提示可能没电梯", "可能没有电梯" in (r.elevator_hint or ""), str(r.elevator_hint))


def test_newness():
    print("\n【新旧程度 / 老破小】")
    fresh = analyze_condition("精装公寓 首次出租 拎包入住", tags="新上|精装")
    check("新装信号 → 分数偏高", fresh.newness_score >= 70, f"{fresh.newness_score}")
    check("记录新装信号", len(fresh.newness_signals) > 0, str(fresh.newness_signals))

    old = analyze_condition("老破小 两室一厅 简装")
    check("老破小 → 标记", old.old_small is True, f"依据={old.old_small_evidence}")
    check("老破小 → 分数明显偏低", old.newness_score <= 30, f"{old.newness_score}")

    village = analyze_condition("城中村 农民房 单间")
    check("城中村/农民房 → 标记为老破小类", village.old_small is True,
          f"依据={village.old_small_evidence}")

    plain = analyze_condition("两室一厅 南北通透")
    check("无信号 → 中性分", plain.newness_score == 50, f"{plain.newness_score}")
    check("无信号 → 不标记老破小", plain.old_small is False)


def test_profile_roundtrip():
    print("\n【需求档案存取】")
    p = Profile(name="_test_profile", city="深圳", stations=["红山", "龙华"],
                price_min=1200, price_max=2500, layouts=["studio", "1b1l"])
    path = p.save()
    check("保存成功", os.path.exists(path), os.path.basename(path))
    loaded = Profile.load("_test_profile")
    check("读回一致", loaded.to_dict() == p.to_dict())
    os.remove(path)
    check("清理测试档案", not os.path.exists(path))


class FakeAmap:
    """假的步行服务：按直线距离折算，用于离线验证匹配链路"""
    available = True
    calls = 0
    cache_hits = 0

    def walking(self, origin, destination):
        from backend.services.amap import haversine_meters
        from backend.services.amap import WalkingResult
        self.calls += 1
        straight = haversine_meters(origin[0], origin[1], destination[0], destination[1])
        # 步行距离取直线的 1.4 倍，速度按 75 米/分钟
        walk = int(straight * 1.4)
        return WalkingResult(distance_m=walk, duration_s=int(walk / 75 * 60))


def test_match_pipeline():
    print("\n【需求匹配链路（内存库 + 假步行服务，完全隔离）】")
    # 用内存数据库：不受真实库与后台采集影响，结果可重复
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=True)()
    station_name = "_测试站"

    station = MetroStation(city="深圳", name=station_name,
                           lng=114.0200, lat=22.6500, coord_source="test")
    db.add(station)
    db.commit()

    def add(title, price, layout, d_lng, d_lat, desc="", tags="", floors=None):
        house = House(
            source="beike", source_url=f"https://example.invalid/{title}",
            title=title, description=desc, tags=tags, city="深圳",
            price=price, layout_key=layout, longitude=114.0200 + d_lng,
            latitude=22.6500 + d_lat, status=0,
            raw_data=floors or "",
        )
        db.add(house)
        return house

    add("[测试]近站便宜单间", 1800, "studio", 0.002, 0.002,
        "精装 电梯房 拎包入住", "新上|精装", "高楼层（20层）")      # 应命中
    add("[测试]近站一房一厅", 2300, "1b1l", 0.004, 0.0,
        "精装修 首次出租", "精装", "中楼层（18层）")                 # 应命中
    add("[测试]超预算", 3500, "studio", 0.002, 0.002, "精装")      # 价格超 → 不候选
    add("[测试]房型不符", 2000, "3b1l", 0.002, 0.002, "精装")      # 房型不符 → 不候选
    add("[测试]离站太远", 1900, "studio", 0.05, 0.05, "精装")      # 直线 > 1km → 淘汰
    add("[测试]老破小", 1700, "studio", 0.002, 0.002,
        "老破小 简装 无电梯")                                      # 老破小 → 淘汰
    db.commit()

    profile = Profile(name="_test_match", city="深圳", stations=[station_name],
                      max_straight_m=1000, max_walk_minutes=20,
                      price_min=1200, price_max=2500,
                      layouts=["studio", "1b1l"], avoid_old_small=True)
    result = match(db, profile, amap=FakeAmap(), compute_walk=True)
    stats = result["stats"]
    titles = [m.title for m in result["matched"]]

    check("匹配成功执行", result["success"] is True)
    # 6 套测试房源：超预算 1 + 房型不符 1 被前置过滤 → 4 条候选
    check("价格与房型过滤生效", stats["priceLayoutCandidates"] == 4,
          f"候选 {stats['priceLayoutCandidates']} 条（排除超预算与房型不符）")
    # 4 条候选中「离站太远」超出 1km → 3 条进入后续判断
    check("直线距离预筛生效", stats["withinStraight"] == 3,
          f"直线达标 {stats['withinStraight']} 条（排除离站太远）")
    check("老破小被排除", "[测试]老破小" not in titles, str(titles))
    check("符合的房源被选出", len(titles) == 2, str(titles))
    check("结果按步行时间排序",
          all(result["matched"][i].walk_minutes <= result["matched"][i + 1].walk_minutes
              for i in range(len(result["matched"]) - 1)),
          str([m.walk_minutes for m in result["matched"]]))
    check("每条都给出符合理由",
          all(len(m.reasons) >= 2 for m in result["matched"]),
          str(result["matched"][0].reasons[:2]) if result["matched"] else "")
    check("电梯状态被如实标注",
          any(m.elevator is True for m in result["matched"]),
          str([(m.title, m.elevator) for m in result["matched"]]))

    # 预算外的房源不应出现
    check("超预算房源未混入", all((m.price or 0) <= 2500 for m in result["matched"]),
          str([m.price for m in result["matched"]]))

    db.close()  # 内存库随会话释放，无需清理


def main():
    print("=" * 66)
    print("条件识别与需求匹配 离线测试")
    print("=" * 66)
    test_elevator()
    test_newness()
    test_profile_roundtrip()
    test_match_pipeline()
    print("\n" + "=" * 66)
    print(f"结果: ✅ 通过 {PASSED} | ❌ 失败 {FAILED}")
    print("=" * 66)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
