"""坐标系转换

中国境内存在两套常用坐标系，混用会造成 50~500 米的系统性偏移：

- **WGS-84**：GPS 原始坐标。维基百科/Wikidata、OpenStreetMap 用的就是它。
- **GCJ-02**：国测局加密坐标（"火星坐标"）。高德地图全系产品（JS API、
  Web 服务、步行/驾车路径规划）使用的都是 GCJ-02。

本项目统一以 **GCJ-02** 为内部存储标准，原因：
1. 房源定位走高德地理编码/POI，拿到的本来就是 GCJ-02；
2. 步行距离用高德路径规划计算，入参必须是 GCJ-02；
3. 前端地图是高德 JS API，也要求 GCJ-02。

因此从 Wikidata 导入的地铁站坐标**必须先转换**再入库，否则算出来的
"步行到站距离"会整体偏移几百米——这是静默的错误，用户很难察觉。

转换算法为国测局公开的经典实现（偏移量由克拉索夫斯基椭球参数推导），
是确定性的数学变换，不是估算。
"""

from __future__ import annotations

import math
from typing import Tuple

# 长半轴 / 偏心率平方（克拉索夫斯基椭球）
A = 6378245.0
EE = 0.00669342162296594323

# 中国大致经纬度范围：超出此范围不做偏移（境外坐标不加密）
LNG_MIN, LNG_MAX = 72.004, 137.8347
LAT_MIN, LAT_MAX = 0.8293, 55.8271


def out_of_china(lng: float, lat: float) -> bool:
    return not (LNG_MIN < lng < LNG_MAX and LAT_MIN < lat < LAT_MAX)


def _transform_lat(lng: float, lat: float) -> float:
    ret = (-100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat
           + 0.2 * math.sqrt(abs(lng)))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * math.pi) + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    ret = (300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat
           + 0.1 * math.sqrt(abs(lng)))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * math.pi) + 40.0 * math.sin(lng / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * math.pi) + 300.0 * math.sin(lng / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """WGS-84 → GCJ-02（用于把 Wikidata/OSM 坐标转成高德可用的坐标）"""
    if out_of_china(lng, lat):
        return lng, lat

    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)

    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - EE * magic * magic
    sqrt_magic = math.sqrt(magic)

    d_lat = (d_lat * 180.0) / ((A * (1 - EE)) / (magic * sqrt_magic) * math.pi)
    d_lng = (d_lng * 180.0) / (A / sqrt_magic * math.cos(rad_lat) * math.pi)

    return lng + d_lng, lat + d_lat


def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """GCJ-02 → WGS-84（导出给 GPS 设备/OSM 时使用；反解为一次逼近）"""
    if out_of_china(lng, lat):
        return lng, lat

    # 正解一次得到偏移量，再反向扣除（精度足够日常使用）
    converted_lng, converted_lat = wgs84_to_gcj02(lng, lat)
    return lng * 2 - converted_lng, lat * 2 - converted_lat


def convert_if_wgs84(lng: float, lat: float, source: str) -> Tuple[float, float, str]:
    """按来源决定是否需要转换，返回 (lng, lat, 说明)

    - wikidata / osm / wgs84 开头的来源 → 需要转成 GCJ-02
    - amap / gcj02 开头的来源 → 原样返回
    """
    s = (source or "").lower()
    if s.startswith(("amap", "gcj", "gaode")):
        return lng, lat, "已是 GCJ-02，无需转换"
    if s.startswith(("wikidata", "osm", "wgs", "wikipedia")):
        new_lng, new_lat = wgs84_to_gcj02(lng, lat)
        return new_lng, new_lat, "WGS-84 → GCJ-02 已转换"
    # 来源不明时保守处理：不做偏移，但如实记录
    return lng, lat, f"来源 {source} 未知，未做坐标系转换"
