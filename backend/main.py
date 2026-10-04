from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.database import init_db
from backend.routers import cities, geo, houses, match, metro, sources
from backend.routers import config as config_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库"""
    init_db()
    print("✅ 数据库初始化完成")
    yield


app = FastAPI(
    title="HouseSearch Local API",
    description="本地租房信息聚合搜索系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - 允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(houses.router, prefix="/api", tags=["houses"])
app.include_router(cities.router, prefix="/api", tags=["cities"])
app.include_router(metro.router, prefix="/api", tags=["metro"])
app.include_router(geo.router, prefix="/api", tags=["geo"])
app.include_router(match.router, prefix="/api", tags=["match"])
app.include_router(sources.router, prefix="/api", tags=["sources"])
app.include_router(config_router.router, prefix="/api", tags=["config"])


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": "1.0.0", "api": "/api"}


# 如果前端构建产物存在，挂载静态文件（vite 的 outDir 为 build，兼容 dist）
# 前端使用 createBrowserRouter，因此需要把未知路径回退到 index.html，否则深链接会 404。
_here = os.path.dirname(os.path.abspath(__file__))
_dist_dir = None
for _folder in ("build", "dist"):
    _candidate = os.path.join(_here, "..", "frontend", _folder)
    if os.path.exists(os.path.join(_candidate, "index.html")):
        _dist_dir = os.path.realpath(_candidate)
        break

if _dist_dir:
    _index_file = os.path.join(_dist_dir, "index.html")
    _assets_dir = os.path.join(_dist_dir, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """返回静态资源本体，找不到则回退到 index.html（SPA 深链接）"""
        # 未匹配到的 /api/* 应保持 404，避免把接口错误伪装成首页
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")

        if full_path:
            target = os.path.realpath(os.path.join(_dist_dir, full_path))
            # 防目录穿越：必须仍位于前端产物目录内
            if target.startswith(_dist_dir + os.sep) and os.path.isfile(target):
                return FileResponse(target)

        return FileResponse(_index_file)

    print(f"📦 已挂载前端静态资源: {_dist_dir}")
