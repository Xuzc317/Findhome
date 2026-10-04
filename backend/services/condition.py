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
