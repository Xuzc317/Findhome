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
    """初始化数据库（创建所有表 + 轻量迁移）

    可重复运行：已存在的表不会被重建，缺失的列会按需补齐。
    """
    Base.metadata.create_all(bind=engine)
    _apply_light_migrations()


# 新增列 -> DDL 片段（SQLite 的 ADD COLUMN 是幂等安全的：先查 PRAGMA 再补）
_LIGHT_MIGRATIONS = {
    "houses": {
        "last_active_time": "DATETIME",
    },
}


def _apply_light_migrations():
    """为已存在的表补齐新增列，避免老库因缺列而查询报错"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, columns in _LIGHT_MIGRATIONS.items():
            if table not in existing_tables:
                continue
            current = {col["name"] for col in inspector.get_columns(table)}
            for column, ddl_type in columns.items():
                if column in current:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
                print(f"🔧 迁移: {table}.{column} 已补齐")


def get_db() -> Session:
    """获取数据库会话（用于依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
