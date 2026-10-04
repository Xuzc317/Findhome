#!/usr/bin/env python3
"""
HouseSearch Local v1 - 演示数据生成脚本

用途：在没有真实爬虫数据时，验证「后端 API + 前端页面」链路是否正常。
所有演示数据标题都带 [示例] 前缀，链接域名为 demo.local，便于与真实采集数据区分。

用法:
    python seed_demo.py          # 写入（幂等，重复执行不会产生重复行）
    python seed_demo.py --clear  # 删除全部演示数据
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import SessionLocal, init_db  # noqa: E402
from backend.models import House  # noqa: E402
from backend.services.dedup import DedupService  # noqa: E402
from backend.services.risk import RiskScorer  # noqa: E402

DEMO_DOMAIN = "https://demo.local"

# (city, district, community, address, price, rent_type, lon, lat, source, title, description, tags)
DEMO_ROWS = [
    ("上海", "浦东新区", "金杨新村", "浦东新区金杨路 750 弄", 4200, 3, 121.5560, 31.2500,
     "douban", "[示例] 金杨新村 一室一厅 整租 近6号线金桥路站",
     "个人房东直租，一室一厅，精装修，家电齐全，近地铁6号线金桥路站步行8分钟。押一付三。", "整租|近地铁|个人"),
    ("上海", "徐汇区", "田林十二村", "徐汇区田林路 120 号", 3600, 1, 121.4180, 31.1830,
     "douban", "[示例] 田林十二村 主卧合租 限女生",
     "合租主卧，室友都是上班族，安静。近9号线桂林路站，可短租。", "合租|主卧|限女生"),
    ("上海", "静安区", "大宁金茂府", "静安区共和新路 2200 弄", 9800, 3, 121.4560, 31.2830,
     "beike", "[示例] 大宁金茂府 两室两厅 精装修 拎包入住",
     "品牌公寓直租，豪华装修，拎包入住，24小时管家服务，看房随时联系，中介勿扰。", "整租|公寓|精装"),
    ("上海", "杨浦区", "同济新村", "杨浦区赤峰路 67 弄", 2800, 2, 121.5010, 31.2870,
     "xianyu", "[示例] 同济新村 单间出租 近10号线同济大学站",
     "单间带独卫，适合学生或刚工作的同学，租金2800元/月，水电自理。", "单间|近地铁|学生"),
    ("上海", "长宁区", "中山公寓", "长宁区中山西路 888 号", 220, 4, 121.4130, 31.2120,
     "xiaohongshu", "[示例] 中山公寓 精品公寓 限时特价 秒杀",
     "ins风网红公寓，豪华高端品质，限时优惠折扣，随时看房，微信同号电话13800138000。", "公寓|特价|网红"),
    ("深圳", "南山区", "科技园", "南山区科苑路 15 号", 6500, 3, 113.9440, 22.5320,
     "douban", "[示例] 科技园 一室一厅 整租 近1号线深大站",
     "整租一室一厅，采光好，家电齐全，近1号线深大站，腾讯滨海大厦通勤15分钟。", "整租|近地铁|通勤"),
    ("深圳", "福田区", "皇岗村", "福田区皇岗路 1002 号", 3200, 1, 114.0640, 22.5340,
     "douban", "[示例] 皇岗村 次卧合租 近7号线皇岗村站",
     "次卧合租，室友两人，公共区域宽敞，近7号线皇岗村站，押一付一。", "合租|次卧|近地铁"),
    ("深圳", "南山区", "海岸城", "南山区海德三道 199 号", 12000, 4, 113.9350, 22.5150,
     "beike", "[示例] 海岸城 服务式公寓 月租 高端品质",
     "海量房源，品牌公寓，服务费另计，正规合同，看房随时，多套可选。", "公寓|高端|服务"),
    ("深圳", "宝安区", "灵芝新村", "宝安区新安街道灵芝路 8 号", 2400, 2, 113.8990, 22.5690,
     "xianyu", "[示例] 灵芝新村 单间 近5号线灵芝站",
     "单间出租，独立卫浴，近5号线灵芝站，周边生活便利。", "单间|近地铁"),
    ("北京", "朝阳区", "望京西园", "朝阳区望京西路 4 号", 5200, 2, 116.4620, 39.9930,
     "douban", "[示例] 望京西园 次卧 近14号线望京站",
     "次卧出租，房子干净，室友程序员，近14号线望京站，可做饭。", "合租|次卧|近地铁"),
    ("北京", "海淀区", "知春里", "海淀区知春路 82 号", 7800, 3, 116.3350, 39.9760,
     "beike", "[示例] 知春里 两室一厅 整租 近10号线知春里站",
     "两室一厅整租，南北通透，家电齐全，近10号线知春里站，业主直租。", "整租|近地铁|业主"),
    ("北京", "昌平区", "天通苑北", "昌平区立汤路 201 号", 180, 2, 116.4180, 40.0850,
     "xiaohongshu", "[示例] 天通苑 单间 超低价 拎包入住",
     "全新装修，首次出租，随时看房，24小时管家服务，电话13900139000。", "单间|全新|特价"),
    ("广州", "天河区", "棠下村", "天河区棠下棠德南路 12 号", 2600, 1, 113.3720, 23.1290,
     "douban", "[示例] 棠下村 主卧合租 近5号线科韵路站",
     "主卧合租，房子带阳台，近5号线科韵路站，生活便利。", "合租|主卧|近地铁"),
    ("杭州", "西湖区", "文三路小区", "西湖区文三路 199 号", 4300, 3, 120.1290, 30.2760,
     "douban", "[示例] 文三路 一居室 整租 近2号线学院路站",
     "一室一厅整租，采光好，近2号线学院路站，适合互联网上班族。", "整租|近地铁"),
]

# 与上面某条跨平台重复（用于演示去重标记）
DEMO_DUPLICATE = ("深圳", "南山区", "科技园", "南山区科苑路 15 号", 6500, 3, 113.9440, 22.5320,
                  "beike", "[示例] 科技园 一室一厅 整租 近1号线深大站",
                  "整租一室一厅，采光好，家电齐全，近1号线深大站，腾讯滨海大厦通勤15分钟。", "整租|近地铁|通勤")


def build_house(row, index: int, base_time: datetime) -> House:
    (city, district, community, address, price, rent_type, lon, lat,
     source, title, description, tags) = row

    return House(
        source=source,
        source_id=f"demo-{source}-{index}",
        source_url=f"{DEMO_DOMAIN}/{source}/{index}",
        title=title,
        description=description,
        city=city,
        district=district,
        area=community,
        community=community,
        address=address,
        longitude=lon,
        latitude=lat,
        price=price,
        rent_type=rent_type,
        room_type={1: "合租", 2: "单间", 3: "整租", 4: "公寓"}.get(rent_type, ""),
        area_size=float(30 + index * 5),
        orientation="南北",
        publish_time=base_time - timedelta(days=index % 7, hours=index % 12),
        crawl_time=datetime.now(),
        publisher="演示数据",
        publisher_id=f"demo-user-{index}",
        images="[]",
        tags=tags,
        raw_data='{"demo": true}',
        status=0,
    )


def clear_demo(db) -> int:
    rows = db.query(House).filter(House.source_url.like(f"{DEMO_DOMAIN}/%")).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)


def seed():
    init_db()
    db = SessionLocal()
    try:
        total_demo = db.query(House).filter(House.source_url.like(f"{DEMO_DOMAIN}/%")).count()
        if total_demo:
            print(f"ℹ️  已存在 {total_demo} 条演示数据（脚本幂等，无需重复写入）")
            print("   如需重建请先执行: python seed_demo.py --clear")
            return

        base_time = datetime.now()
        dedup = DedupService(db)
        inserted = 0

        for index, row in enumerate(DEMO_ROWS, start=1):
            house = build_house(row, index, base_time)

            # 与库中已有数据比对，命中则标记为重复（前端默认会隐藏）
            matched = dedup.find_duplicate(house)
            if matched is not None:
                house.is_duplicate = True
                house.duplicate_of = matched.id

            scores = RiskScorer.score_house(house)
            house.agent_score = scores["agent"]
            house.ad_score = scores["ad"]
            house.suspicious_score = scores["suspicious"]
            house.confidence_score = max(
                0, 100 - max(scores["agent"], scores["ad"], scores["suspicious"])
            )

            db.add(house)
            inserted += 1

        # 跨平台重复样本
        dup_house = build_house(DEMO_DUPLICATE, 900, base_time)
        matched = dedup.find_duplicate(dup_house)
        if matched is not None:
            dup_house.is_duplicate = True
            dup_house.duplicate_of = matched.id
        scores = RiskScorer.score_house(dup_house)
        dup_house.agent_score = scores["agent"]
        dup_house.ad_score = scores["ad"]
        dup_house.suspicious_score = scores["suspicious"]
        dup_house.confidence_score = max(
            0, 100 - max(scores["agent"], scores["ad"], scores["suspicious"])
        )
        db.add(dup_house)
        inserted += 1

        db.commit()

        print(f"✅ 演示数据写入完成: {inserted} 条")
        print(f"   数据库: {db.get_bind().url}")
        print("   验证: curl 'http://localhost:8000/api/v3/houses?pageSize=5'")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="写入 / 清理演示数据")
    parser.add_argument("--clear", action="store_true", help="删除全部演示数据")
    args = parser.parse_args()

    if args.clear:
        init_db()
        db = SessionLocal()
        try:
            count = clear_demo(db)
            print(f"🗑️  已删除 {count} 条演示数据")
        finally:
            db.close()
        return

    seed()


if __name__ == "__main__":
    main()
