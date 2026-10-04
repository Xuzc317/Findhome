from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from backend.config import DATA_DIR, PROJECT_ROOT, get_settings
from backend.models import Base

settings = get_settings()


def normalize_db_url(url: str) -> str:
    """把 SQLite 相对路径解析为项目根目录下的绝对路径。

    .env 里常见的 `sqlite:///data/houses.db` 会随工作目录漂移，
    这里统一固定到 <项目根>/data/houses.db。
    """
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith("sqlite:////"):
        raw_path = url[len(prefix):]
        path = Path(raw_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"{prefix}{path}"
    return url


DATABASE_URL = normalize_db_url(settings.database_url)
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    echo=False,
)

# SQLite 外键支持
if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# autoflush=True：去重/查重查询执行前会先 flush 挂起的新对象，
# 否则同一批次内刚 add 的房源对查询不可见，去重标记会失效。
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)


def init_db():
    """初始化数据库（创建所有表）"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """获取数据库会话（用于依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
