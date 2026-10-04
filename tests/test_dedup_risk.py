#!/usr/bin/env python3
"""
去重与风险评分测试（离线，使用内存 SQLite）

覆盖链路上的"去重 → 风险标记"环节，不联网、不触发平台风控。

运行:
    python tests/test_dedup_risk.py
"""

import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.models import Base, House  # noqa: E402
from backend.services.dedup import DedupService  # noqa: E402
from backend.services.risk import RiskScorer  # noqa: E402

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


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=True)()


def house(**kwargs) -> House:
    data = {
        "source": "douban",
        "source_url": "https://www.douban.com/group/topic/1",
        "title": "整租 一室一厅 3500元/月",
        "city": "北京",
        "price": 3500,
        "rent_type": 3,
        "crawl_time": datetime.now(),
    }
    data.update(kwargs)
    return House(**data)


def test_url_dedup():
    print("\n【链接去重】")
    db = make_session()
    db.add(house())
    db.commit()

    dedup = DedupService(db)
    same = dedup.find_duplicate(house())
    check("同链接判定为重复", same is not None, same.source_url if same else "未命中")

    other = dedup.find_duplicate(house(source_url="https://www.douban.com/group/topic/2"))
    check("不同链接不算重复", other is None)


def test_cross_platform_dedup():
    print("\n【跨平台重复检测】")
    db = make_session()
    db.add(house())
    db.commit()

    dedup = DedupService(db)
    # 标题 + 价格 + 城市 相同，来源不同 → 视为跨平台重复
    cross = dedup.find_duplicate(house(
        source="beike",
        source_url="https://sz.zu.ke.com/zufang/SZ1.html",
    ))
    check("跨平台同标题同价格判定为重复", cross is not None,
          cross.source if cross else "未命中")

    # 价格不同 → 不算重复
    different = dedup.find_duplicate(house(
        source="beike",
        source_url="https://sz.zu.ke.com/zufang/SZ2.html",
        price=9900,
    ))
    check("价格不同不算重复", different is None)

    # 城市不同 → 不算重复
    other_city = dedup.find_duplicate(house(
        source="beike",
        source_url="https://sz.zu.ke.com/zufang/SZ3.html",
        city="深圳",
    ))
    check("城市不同不算重复", other_city is None)


def test_community_similarity_dedup():
    print("\n【同小区 + 相似标题】")
    db = make_session()
    db.add(house(
        source="douban",
        source_url="https://www.douban.com/group/topic/10",
        title="望京西园 次卧出租 采光好 近地铁",
        community="望京西园",
        price=3000,
        city="北京",
    ))
    db.commit()

    dedup = DedupService(db)
    similar = dedup.find_duplicate(house(
        source="beike",
        source_url="https://bj.zu.ke.com/zufang/BJ1.html",
        title="望京西园 次卧出租 采光好 近地铁站",
        community="望京西园",
        price=3000,
        city="北京",
    ))
    check("同小区同价位且标题高度相似 → 重复", similar is not None,
          similar.title if similar else "未命中")

    dissimilar = dedup.find_duplicate(house(
        source="beike",
        source_url="https://bj.zu.ke.com/zufang/BJ2.html",
        title="完全不同的另一套房源描述内容",
        community="望京西园",
        price=3000,
        city="北京",
    ))
    check("标题不相似 → 不判定重复", dissimilar is None)


def test_risk_scoring():
    print("\n【风险评分（可解释规则）】")
    # 干净房源：无中介词、无营销词、描述充分、价格合理
    clean = house(
        title="北二环一居室出租",
        description="业主直租，房子干净整洁，小区安静，周边生活便利，适合长期居住。",
        price=6500,
        city="北京",
    )
    scores = RiskScorer.score_house(clean)
    check("三个维度都存在", {"agent", "ad", "suspicious"} <= set(scores), str(scores))
    check("分值在 0-100 内", all(0 <= v <= 100 for v in scores.values()), str(scores))
    check("干净房源中介分低", scores["agent"] <= 20, f"agent={scores['agent']}")

    # 中介特征：关键词 + 机构发布者 + 异常低价
    agentish = house(
        title="品牌公寓 海量房源 多套可选 看房随时联系 中介服务费",
        description="本公司专业代理，正规合同，经纪人一对一服务，微信同号。",
        publisher="某某公寓管理公司",
        price=400,
        city="北京",
    )
    agent_scores = RiskScorer.score_house(agentish)
    check("中介特征房源中介分高", agent_scores["agent"] > 50,
          f"agent={agent_scores['agent']}")

    agentish.agent_score = agent_scores["agent"]
    agentish.ad_score = agent_scores["ad"]
    agentish.suspicious_score = agent_scores["suspicious"]
    reasons = RiskScorer.get_risk_reasons(agentish)
    check("能给出可读的风险原因", len(reasons) > 0, " / ".join(reasons[:2]))

    # 营销文案
    ad = house(
        title="豪华精装修 拎包入住 限时特价 秒杀 网红ins风",
        description="高端品质，24小时管家服务，随时看房，首次出租，全新装修。",
        price=8000, city="上海",
    )
    ad_scores = RiskScorer.score_house(ad)
    check("营销文案广告分高", ad_scores["ad"] > 30, f"ad={ad_scores['ad']}")

    # 异常：价格远低于城市下限 + 描述过短
    weird = house(title="超低价好房", description="", price=150, city="北京")
    weird_scores = RiskScorer.score_house(weird)
    check("异常房源异常分高", weird_scores["suspicious"] > 30,
          f"suspicious={weird_scores['suspicious']}")

    check("评分可重复（同输入同输出）",
          RiskScorer.score_house(clean) == scores)


def test_risk_filter_semantics():
    print("\n【风险分与可信度的关系】")
    db = make_session()
    h = house(price=6500, description="业主直租，房子干净整洁，小区安静，周边生活便利。")
    scores = RiskScorer.score_house(h)
    h.agent_score = scores["agent"]
    h.ad_score = scores["ad"]
    h.suspicious_score = scores["suspicious"]
    h.confidence_score = max(0, 100 - max(scores.values()))
    db.add(h)
    db.commit()
    check("可信度 = 100 - 最大风险分",
          h.confidence_score == 100 - max(scores.values()),
          f"conf={h.confidence_score} scores={scores}")


def main():
    print("=" * 66)
    print("去重与风险评分测试（内存 SQLite，无需联网）")
    print("=" * 66)
    test_url_dedup()
    test_cross_platform_dedup()
    test_community_similarity_dedup()
    test_risk_scoring()
    test_risk_filter_semantics()
    print("\n" + "=" * 66)
    print(f"结果: ✅ 通过 {PASSED} | ❌ 失败 {FAILED}")
    print("=" * 66)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
