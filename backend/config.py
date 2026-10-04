"""应用配置

所有路径均以项目根目录为基准，因此无论从哪个目录启动进程都能读到同一份
.env 与同一个 SQLite 文件。
"""

from functools import lru_cache
from pathlib import Path
import re

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录 = backend/ 的上一级
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """应用配置（可通过 .env 或环境变量覆盖）"""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库（相对路径会在 database.py 中按项目根目录解析）
    database_url: str = f"sqlite:///{DATA_DIR / 'houses.db'}"

    # 高德地图
    # 后端 REST 用（地理编码/POI/步行路径/地铁）：服务平台必须选「Web服务」
    amap_web_key: str = ""
    # 前端地图用（JS API）：服务平台选「Web端(JS API)」，配套安全密钥
    # 这两项只在后端 .env 保存，由 /api/config 运行时下发，
    # 不写进 frontend/.env，避免被 Vite 内联进静态产物
    amap_key: str = ""
    amap_security_code: str = ""

    # 服务器
    host: str = "0.0.0.0"
    port: int = 8000

    # 爬虫
    crawl_interval: int = 2

    # 平台 Cookie
    xiaohongshu_cookie: str = ""
    beike_cookie: str = ""
    xianyu_cookie: str = ""
    douban_cookie: str = ""

    # 通勤目的地
    commute_destination: str = ""
    commute_destination_lng: float = 0.0
    commute_destination_lat: float = 0.0

    # 高德「Web服务」Key（地理编码/POI/步行路径/地铁线路；与前端 JS Key 不同）
    # 复用上面的 amap_web_key 字段

    # ==================== 大模型 ====================
    # 供应商选择: auto / deepseek / doubao / none
    llm_provider: str = "auto"
    llm_timeout: float = 120.0
    # 抽取任务关闭"思考"可大幅提速降本（实测 67s→1.7s）；
    # 若用的是非推理模型可保持 disabled，模型不支持时会自动去掉该参数重试
    llm_thinking: str = "disabled"
    llm_max_images: int = 2          # 单条房源最多分析几张图（控制成本）

    # DeepSeek（文本，OpenAI 兼容）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # 豆包 / 火山方舟（文本 + 图片理解）
    doubao_api_key: str = ""         # 也可用 ARK_API_KEY
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str = ""           # 填方舟的「接入点 ID」(ep-xxxx) 或模型名

    # 是否允许把房源图片提交给大模型做位置/信息抽取
    llm_vision_enabled: bool = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# 明显的占位符/示例值，视为"未配置"。
# 否则 .env.example 拷过来的 your_xxx_here 会被当成真 Key，
# 一边报"已配置"一边被平台拒绝，很难排查。
PLACEHOLDER_PATTERN = re.compile(
    r"(your[_-]|_here$|^xxx|changeme|填入|示例|placeholder|^<.*>$)", re.IGNORECASE
)


def looks_like_placeholder(value: str) -> bool:
    """判断一个 Key/Cookie 是否仍是模板占位符"""
    if not value:
        return True
    value = value.strip()
    if len(value) < 8:
        return True
    return bool(PLACEHOLDER_PATTERN.search(value))


def is_configured(value: str) -> bool:
    """既非空、也不是占位符，才算真正配置了"""
    return bool(value) and not looks_like_placeholder(value)
