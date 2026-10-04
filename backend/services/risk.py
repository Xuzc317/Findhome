import re
from typing import List, Dict
from backend.models import House


# 中介关键词
AGENT_KEYWORDS = [
    "中介", "经纪人", "置业顾问", "看房随时", "多套可选",
    "海量房源", "全市房源", "佣金", "服务费", "管理费",
    "品牌公寓", "长租公寓", "公寓直租", "物业直租",
    "委托", "独家", "代理", "正规合同", "公司",
    "看房联系", "微信同号", "电话",
]

# 广告/营销关键词
AD_KEYWORDS = [
    "精装修", "拎包入住", "豪华", "高端", "品质",
    "秒杀", "特价", "限时", "优惠", "折扣",
    "首次出租", "全新装修", "网红", "ins风",
    "随时看房", "24小时", "管家服务",
]

# 异常价格范围（按城市粗略估算，需要更精确的可后续完善）
CITY_PRICE_RANGES = {
    "北京": (800, 30000),
    "上海": (800, 30000),
    "深圳": (600, 25000),
    "广州": (500, 20000),
    "杭州": (600, 20000),
    "成都": (400, 15000),
    "武汉": (400, 12000),
    "西安": (400, 10000),
    "南京": (500, 15000),
    "重庆": (400, 12000),
}

# 模板化文本特征
TEMPLATE_PATTERNS = [
    r"\d+室\d+厅",
    r"\d+平米",
    r"距\d+号线",
    r"\d+分钟",
    r"随时看房",
    r"押一付[一二三]",
]


class RiskScorer:
    """房源风险评分器"""

    @staticmethod
    def score_house(house: House) -> Dict[str, int]:
        """
        对单个房源进行风险评分
        返回: {"agent": 0-100, "ad": 0-100, "suspicious": 0-100}
        """
        text = f"{house.title or ''} {house.description or ''} {house.tags or ''}"
        text = text.lower()

        # 1. 中介评分
        agent_score = RiskScorer._calc_agent_score(text, house)

        # 2. 广告评分
        ad_score = RiskScorer._calc_ad_score(text, house)

        # 3. 异常评分
        suspicious_score = RiskScorer._calc_suspicious_score(house, text)

        return {
            "agent": min(100, agent_score),
            "ad": min(100, ad_score),
            "suspicious": min(100, suspicious_score),
        }

    @staticmethod
    def _calc_agent_score(text: str, house: House) -> int:
        """计算中介概率分数"""
        score = 0

        # 关键词匹配
        for kw in AGENT_KEYWORDS:
            if kw in text:
                score += 10

        # 发布者名称判断
        publisher = (house.publisher or "").lower()
        if any(x in publisher for x in ["公寓", "置业", "地产", "中介", "管家"]):
            score += 30

        # 标题长度（中介标题通常较长且模板化）
        title = house.title or ""
        if len(title) > 30:
            score += 5

        # 价格异常低（引流）
        if house.price and house.price < 500:
            score += 20

        return score

    @staticmethod
    def _calc_ad_score(text: str, house: House) -> int:
        """计算广告/营销分数"""
        score = 0

        for kw in AD_KEYWORDS:
            if kw in text:
                score += 8

        # 模板化程度
        template_matches = 0
        for pattern in TEMPLATE_PATTERNS:
            if re.search(pattern, text):
                template_matches += 1
        score += template_matches * 5

        # 标签过多（营销特征）
        tags = house.tags or ""
        if len(tags.split("|")) > 5:
            score += 10

        return score

    @staticmethod
    def _calc_suspicious_score(house: House, text: str) -> int:
        """计算异常分数"""
        score = 0
        price = house.price or 0
        city = house.city or ""

        # 价格异常
        min_price, max_price = CITY_PRICE_RANGES.get(city, (300, 50000))
        if price > 0:
            if price < min_price:
                score += 30
            if price > max_price * 2:
                score += 20

        # 缺少关键信息
        if not house.description or len(house.description) < 20:
            score += 15

        # 标题和正文严重不符（简单判断）
        if house.title and house.description:
            title_words = set(house.title.split())
            desc_words = set(house.description.split())
            if len(title_words) > 3:
                overlap = len(title_words & desc_words) / len(title_words)
                if overlap < 0.1:
                    score += 20

        # 联系方式过多（引流特征）
        phone_pattern = r"1[3-9]\d{9}"
        phones = re.findall(phone_pattern, text)
        if len(phones) > 2:
            score += 15

        return score

    @staticmethod
    def get_risk_reasons(house: House) -> List[str]:
        """获取风险原因列表（用于展示）"""
        reasons = []
        text = f"{house.title or ''} {house.description or ''} {house.tags or ''}"

        if house.agent_score > 50:
            matched = [kw for kw in AGENT_KEYWORDS if kw in text]
            if matched:
                reasons.append(f"检测到中介关键词: {', '.join(matched[:3])}")
            if house.publisher and any(x in house.publisher for x in ["公寓", "地产"]):
                reasons.append("发布者为机构/公寓")

        if house.ad_score > 50:
            reasons.append("文案营销特征明显")

        if house.suspicious_score > 50:
            if house.price and house.price < 500:
                reasons.append("价格异常偏低")
            if not house.description or len(house.description) < 20:
                reasons.append("房源描述过短")

        return reasons
