"""房源条件识别：电梯 / 新旧程度 / 老破小

用户的核心诉求里有两条平台没有结构化字段的条件：
「希望房子有电梯」「新一点，不要老破小」。

这里只从**平台原文**（标题、正文、标签、楼层描述）中识别，
识别不出来就如实标为"未知"，并明确区分：
- `elevator`：文本**明确写了**有/无电梯（事实）
- `elevator_hint`：由楼层推断（如"高楼层（33层）"→ 几乎必有电梯），
  属于**推断**，界面与报告里必须标注，不能当成事实

为什么坚持这个区分：把推断当事实会让用户白跑一趟看房——
"我以为有电梯"比"没写"更糟。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ---------- 电梯 ----------
# 否定式必须先匹配，否则 "无电梯" 会因为含 "电梯" 被误判为有电梯
ELEVATOR_NEGATIVE = [
    r"无电梯", r"没有电梯", r"不带电梯", r"不含电梯",
    r"楼梯房", r"楼梯楼", r"步梯", r"爬楼梯", r"走楼梯",
]
ELEVATOR_POSITIVE = [
    r"电梯房", r"有电梯", r"带电梯", r"电梯直达", r"电梯入户",
    r"独立电梯", r"电梯楼", r"高层电梯",
    # 兜底：只要出现"电梯"且没有命中否定式，就认为写了电梯。
    # 实测"花园小区电梯大单间""电梯4楼"这类写法很常见，
    # 早先只列了"电梯房/有电梯"等固定搭配，导致明确写了电梯却被判为未标注。
    r"电梯",
]

# ---------- 新旧 ----------
NEW_STRONG = [
    r"新上", r"首次出租", r"全新", r"新房", r"新装修", r"重新装修",
    r"新小区", r"新楼盘", r"刚装修", r"品牌公寓", r"长租公寓",
]
NEW_MEDIUM = [
    r"精装", r"豪装", r"精装修", r"豪华装修", r"拎包入住", r"家电齐全",
]
OLD_STRONG = [
    r"老破小", r"老旧", r"老房子", r"老小区", r"农民房", r"城中村",
    r"自建房", r"旧楼", r"平米?老", r"简装", r"毛坯", r"老旧装修",
]
OLD_MEDIUM = [r"楼梯房", r"无电梯", r"步梯"]

# 楼层信息（贝壳描述里有 "高楼层（33层）" 这样的文本）
RE_FLOOR = re.compile(r"(低|中|高|顶|底)楼层\s*[（(]?\s*(\d+)\s*层")
# 楼层高度阈值：超过这个层数基本不可能没有电梯
ELEVATOR_FLOOR_THRESHOLD = 7


@dataclass
class ConditionResult:
    """条件识别结果（事实与推断严格分开）"""
    elevator: Optional[bool] = None          # 文本明确写了：True 有 / False 无 / None 未知
    elevator_evidence: Optional[str] = None  # 判定依据原文
    elevator_hint: Optional[str] = None      # 由楼层推断的提示（不是事实）
    newness_score: int = 50                  # 0-100，越高越新
    newness_signals: List[str] = field(default_factory=list)
    old_small: bool = False                  # 命中"老破小"类负面特征
    old_small_evidence: Optional[str] = None
    total_floors: Optional[int] = None
    floor_text: Optional[str] = None


def _first_match(text: str, patterns: List[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def analyze_condition(*texts: Optional[str],
                      tags: Optional[str] = None,
                      floor_text: Optional[str] = None) -> ConditionResult:
    """从平台原文中识别电梯 / 新旧 / 老破小

    Args:
        texts: 标题、正文等（按可信度从高到低）
        tags: 平台标签（如贝壳的 精装|近地铁|新上）
        floor_text: 楼层描述（如 "高楼层（33层）"）
    """
    result = ConditionResult()
    blob = " ".join(t for t in list(texts) + [tags] if t)
    if not blob.strip() and not floor_text:
        return result

    # ---------- 电梯：先否定，再肯定 ----------
    negative = _first_match(blob, ELEVATOR_NEGATIVE)
    if negative:
        result.elevator = False
        result.elevator_evidence = negative
    else:
        positive = _first_match(blob, ELEVATOR_POSITIVE)
        if positive:
            result.elevator = True
            result.elevator_evidence = positive

    # ---------- 楼层推断（仅作为提示，不写成事实）----------
    if floor_text:
        result.floor_text = floor_text.strip()
        match = RE_FLOOR.search(floor_text)
        if match:
            try:
                result.total_floors = int(match.group(2))
            except (TypeError, ValueError):
                result.total_floors = None
        if result.elevator is None and result.total_floors:
            if result.total_floors >= ELEVATOR_FLOOR_THRESHOLD:
                result.elevator_hint = (
                    f"该楼共 {result.total_floors} 层，实际几乎必有电梯（推断，建议确认）"
                )
            else:
                result.elevator_hint = (
                    f"该楼仅 {result.total_floors} 层，可能没有电梯（推断，建议确认）"
                )

    # ---------- 新旧评分 ----------
    score = 50
    for pattern in NEW_STRONG:
        match = re.search(pattern, blob)
        if match:
            score += 20
            result.newness_signals.append(match.group(0))
            break
    for pattern in NEW_MEDIUM:
        match = re.search(pattern, blob)
        if match:
            score += 12
            result.newness_signals.append(match.group(0))
            break
    old_match = _first_match(blob, OLD_STRONG)
    if old_match:
        score -= 35
        result.old_small = True
        result.old_small_evidence = old_match
        result.newness_signals.append(f"负面:{old_match}")
    else:
        stair = _first_match(blob, OLD_MEDIUM)
        if stair:
            score -= 15
            result.newness_signals.append(f"负面:{stair}")

    result.newness_score = max(0, min(100, score))
    return result


def condition_summary(result: ConditionResult) -> str:
    """给报告用的一句话摘要"""
    parts = []
    if result.elevator is True:
        parts.append(f"电梯：有（原文“{result.elevator_evidence}”）")
    elif result.elevator is False:
        parts.append(f"电梯：无（原文“{result.elevator_evidence}”）")
    elif result.elevator_hint:
        parts.append(f"电梯：未标注（{result.elevator_hint}）")
    else:
        parts.append("电梯：未标注，需自行确认")

    parts.append(f"新旧分 {result.newness_score}")
    if result.newness_signals:
        parts.append("信号：" + "/".join(result.newness_signals[:4]))
    if result.old_small:
        parts.append("⚠️ 含老破小类特征")
    return "；".join(parts)


# ---------- 合租判定（闲鱼/小红书标题没有结构化租型，需要按文本判断）----------
SHARED_STRONG = [
    r"合租", r"找室友", r"招室友", r"拼租", r"分租", r"求合租",
    r"主卧出租", r"次卧出租", r"床位", r"合住", r"搭子",
]
SHARED_WEAK = [r"主卧", r"次卧", r"室友"]

# 明确的"整租"信号：出现这些就不按合租处理
WHOLE_STRONG = [
    r"整租", r"独门独户", r"独立厨卫", r"独立卫浴", r"独立阳台",
    r"一房一厅", r"两房一厅", r"三房一厅",
    # 泛化的 "N室M厅 / N房M厅"（阿拉伯数字与中文数字都要覆盖）
    r"\d\s*[室房]\s*\d?\s*厅",
    r"[一两二三四五六七八九]\s*[室房]\s*[一两二三]\s*厅",
    r"[一两二三四五六七八九]居室?",
    r"\d\s*居室?",
]

RE_WHOLE = re.compile("|".join(WHOLE_STRONG))
RE_SHARED_STRONG = re.compile("|".join(SHARED_STRONG))
RE_SHARED_WEAK = re.compile("|".join(SHARED_WEAK))


def looks_shared(*texts: Optional[str]) -> bool:
    """判断一条房源是不是"合租"（只租其中一间，非独立空间）

    规则：出现明确的合租词 → 合租；
    只出现"主卧/次卧"这类弱信号、且没有整租信号 → 仍按合租处理；
    出现明确整租信号（整租/一房一厅/独立厨卫…）→ 不算合租。
    """
    blob = " ".join(t for t in texts if t)
    if not blob:
        return False
    if RE_SHARED_STRONG.search(blob):
        return True
    if RE_WHOLE.search(blob):
        return False
    return bool(RE_SHARED_WEAK.search(blob))


def infer_rent_type(*texts: Optional[str]) -> int:
    """从文本推断出租类型：1合租 3整租 4公寓 0未知"""
    blob = " ".join(t for t in texts if t)
    if not blob:
        return 0
    if re.search(r"公寓|apartment|loft", blob, re.I) and not RE_SHARED_STRONG.search(blob):
        return 4
    if looks_shared(blob):
        return 1
    if RE_WHOLE.search(blob) or re.search(r"单间|开间|大单间", blob):
        return 3
    return 0


# ---------- "求租"帖识别 ----------
# 这些是"找房的人"发的，不是房源。混进结果会让用户白点。
WANTED_PATTERNS = [
    r"^求租", r"^求房", r"^寻租", r"^找房", r"^想租", r"^求推荐",
    r"求租", r"寻租", r"求房源", r"找房子", r"找一房", r"找单间",
    r"有没有.*(出租|转租).*的", r"有的老板", r"求介绍", r"中介勿扰$",
    r"预算.*求", r"想找个", r"需要租",
]


def looks_wanted(*texts: Optional[str]) -> bool:
    """判断一条信息是不是"求租"帖（发布者在找房，而非出租）"""
    blob = " ".join(t for t in texts if t)
    if not blob:
        return False
    for pattern in WANTED_PATTERNS:
        if re.search(pattern, blob):
            return True
    return False
