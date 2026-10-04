"""全局常量：数据源元信息、城市列表

被 routers（cities/sources）与前端展示共同依赖，统一维护避免多处硬编码不一致。
"""

# 数据源元信息（key 需与 House.source 保持一致）
SOURCE_CONFIGS = {
    "douban": {"display_name": "豆瓣租房", "needs_login": False},
    "beike": {"display_name": "贝壳找房", "needs_login": True},
    "xianyu": {"display_name": "闲鱼", "needs_login": True},
    "xiaohongshu": {"display_name": "小红书", "needs_login": True},
    "58": {"display_name": "58同城", "needs_login": False},
    "ziroom": {"display_name": "自如", "needs_login": False},
}

# 前端筛选栏默认展示的数据源顺序（不含 all，前端会自行插入“全部”）
DEFAULT_CITY_SOURCES = ["douban", "beike", "xianyu", "xiaohongshu"]

# 城市下拉框默认城市（即使数据库还没有数据也保证前端可用）
DEFAULT_CITIES = [
    "上海", "北京", "深圳", "广州", "杭州", "成都",
    "武汉", "西安", "南京", "重庆", "苏州", "天津", "长沙",
]


def display_source(source: str) -> str:
    """获取数据源中文显示名"""
    return SOURCE_CONFIGS.get(source, {}).get("display_name", source)
