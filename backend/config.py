"""应用配置

所有路径均以项目根目录为基准，因此无论从哪个目录启动进程都能读到同一份
.env 与同一个 SQLite 文件。
"""

from functools import lru_cache
from pathlib import Path

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
    amap_key: str = ""
    amap_web_key: str = ""

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()
