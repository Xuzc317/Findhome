"""房型解析

按用户确认的口径归档（以卧室数为准）：
    单间 / 1房1厅 / 2房1厅 / 3房1厅 / 4房及以上

只从平台原文（标题、正文、平台给的房型字段）里解析，解析不出就留空，
绝不用面积或价格去"推"一个房型出来。

支持的常见写法：
    3室2厅1卫 / 3房2厅 / 两室一厅 / 一居室 / 1居室 / 单间 / 开间 / 主卧 / 次卧
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# 房型档位（与前端筛选项一一对应）
LAYOUT_OPTIONS = [
    {"key": "studio", "label": "单间"},
    {"key": "1b1l", "label": "1房1厅"},
    {"key": "2b1l", "label": "2房1厅"},
    {"key": "3b1l", "label": "3房1厅"},
    {"key": "4b+", "label": "4房及以上"},
]

LAYOUT_LABELS = {item["key"]: item["label"] for item in LAYOUT_OPTIONS}

CN_NUMBERS = {
    "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

NUM = r"(?:\d{1,2}|[一两二三四五六七八九十])"

# N室M厅 / N房M厅（最可靠）
RE_ROOMS_HALLS = re.compile(rf"({NUM})\s*[室房]\s*({NUM})\s*厅")
# N室M卫（无厅数信息，但能确定卧室数）
RE_ROOMS_BATHS = re.compile(rf"({NUM})\s*[室房]\s*({NUM})\s*卫")
# N室 / N房（后面不跟厅或卫，避免与上面重复）
RE_ROOMS_ONLY = re.compile(rf"({NUM})\s*[室房](?!\s*[厅卫])")
# N居室
RE_JU_SHI = re.compile(rf"({NUM})\s*居室?")
# 单间类
RE_STUDIO = re.compile(r"(单间|开间|床位|studio|主卧|次卧|隔断间|厅卧)", re.IGNORECASE)
# 合租
RE_SHARED = re.compile(r"(合租|找室友|招室友|拼租|分租)")


def _to_int(token: str) -> Optional[int]:
    if token is None:
        return None
    token = token.strip()
    if token.isdigit():
        value = int(token)
        return value if 0 <= value <= 20 else None
    return CN_NUMBERS.get(token)


def layout_key_of(bedrooms: Optional[int]) -> Optional[str]:
    """卧室数 → 档位 key"""
    if bedrooms is None:
        return None
    if bedrooms <= 0:
        return "studio"
    if bedrooms == 1:
        return "1b1l"
    if bedrooms == 2:
        return "2b1l"
    if bedrooms == 3:
        return "3b1l"
    return "4b+"


@dataclass
class LayoutResult:
    bedrooms: Optional[int] = None
    living_rooms: Optional[int] = None
    layout_key: Optional[str] = None
    confidence: Optional[int] = None
    evidence: Optional[str] = None
    is_shared: bool = False

    @property
    def label(self) -> str:
        return LAYOUT_LABELS.get(self.layout_key or "", "")


def parse_layout(*texts: Optional[str],
                 rent_type: int = 0,
                 room_type: Optional[str] = None) -> LayoutResult:
    """从若干段文本中解析房型。

    Args:
        texts: 依次尝试的文本（一般传 标题、正文）
        rent_type: 平台/既有解析得到的出租类型（1合租 2单间 3整租 4公寓）
        room_type: 平台给出的房型字段
    """
    blob = " ".join(t for t in list(texts) + [room_type] if t).strip()
    result = LayoutResult()

    if not blob:
        # 完全没有文本时，只能靠出租类型给一个低置信度结论
        if rent_type in (1, 2):
            return LayoutResult(bedrooms=0, layout_key="studio",
                                confidence=40, is_shared=(rent_type == 1),
                                evidence="仅依据出租类型=合租/单间")
        return result

    result.is_shared = bool(RE_SHARED.search(blob))

    # 1) N室M厅 —— 最可靠
    match = RE_ROOMS_HALLS.search(blob)
    if match:
        bedrooms = _to_int(match.group(1))
        halls = _to_int(match.group(2))
        if bedrooms is not None:
            return LayoutResult(
                bedrooms=bedrooms, living_rooms=halls,
                layout_key=layout_key_of(bedrooms),
                confidence=95, evidence=match.group(0), is_shared=result.is_shared,
            )

    # 2) N室M卫 —— 能确定卧室数
    match = RE_ROOMS_BATHS.search(blob)
    if match:
        bedrooms = _to_int(match.group(1))
        if bedrooms is not None:
            return LayoutResult(
                bedrooms=bedrooms,
                layout_key=layout_key_of(bedrooms),
                confidence=88, evidence=match.group(0), is_shared=result.is_shared,
            )

    # 3) N居室
    match = RE_JU_SHI.search(blob)
    if match:
        bedrooms = _to_int(match.group(1))
        if bedrooms is not None:
            return LayoutResult(
                bedrooms=bedrooms,
                layout_key=layout_key_of(bedrooms),
                confidence=85, evidence=match.group(0), is_shared=result.is_shared,
            )

    # 4) N室 / N房
    match = RE_ROOMS_ONLY.search(blob)
    if match:
        bedrooms = _to_int(match.group(1))
        if bedrooms is not None:
            return LayoutResult(
                bedrooms=bedrooms,
                layout_key=layout_key_of(bedrooms),
                confidence=80, evidence=match.group(0), is_shared=result.is_shared,
            )

    # 5) 单间类字样
    match = RE_STUDIO.search(blob)
    if match:
        return LayoutResult(
            bedrooms=0, layout_key="studio", confidence=75,
            evidence=match.group(0), is_shared=result.is_shared,
        )

    # 6) 兜底：出租类型
    if rent_type in (1, 2):
        return LayoutResult(
            bedrooms=0, layout_key="studio", confidence=45,
            evidence=f"仅依据出租类型={rent_type}", is_shared=(rent_type == 1),
        )
    if rent_type == 4:
        return LayoutResult(
            bedrooms=0, layout_key="studio", confidence=30,
            evidence="仅依据出租类型=公寓", is_shared=False,
        )

    return result
