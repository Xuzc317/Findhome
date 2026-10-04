from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.constants import SOURCE_CONFIGS
from backend.crawlers.manager import CrawlerManager
from backend.database import get_db
from backend.models import SourceConfig, House, CrawlLog
from backend.schemas import SourceStatus, CrawlRequest, CrawlResponse
from datetime import datetime
from typing import List

router = APIRouter()


@router.get("/sources/health")
async def probe_sources_health(
    probe: bool = Query(False, description="true 时执行真实网络探针（较慢，10~30 秒）"),
    db: Session = Depends(get_db),
):
    """数据源能力与状态

    - probe=false（默认）：只返回静态能力声明与库存统计，不发起网络请求
    - probe=true：对每个平台发起真实请求并解析，返回真实可用性（含失败原因）

    这是“平台访问 → 搜索 → 解析 → 入库 → API”链路中，把平台真实状态
    暴露给调用方的一环，避免前端把“被风控”误读成“没有房源”。
    """
    manager = CrawlerManager(db)

    if not probe:
        data = []
        for source, crawler_class in manager.CRAWLERS.items():
            data.append({
                "source": source,
                "display_name": crawler_class.DISPLAY_NAME,
                "needs_login": crawler_class.NEEDS_LOGIN,
                "detail_available": getattr(crawler_class, "DETAIL_AVAILABLE", True),
                "detail_unavailable_reason": getattr(
                    crawler_class, "DETAIL_UNAVAILABLE_REASON", ""),
                "supported_cities": list(getattr(crawler_class, "SUPPORTED_CITIES", {})),
                "houses_count": db.query(House).filter(House.source == source).count(),
                "probed": False,
            })
        return {"success": True, "code": 0, "data": data}

    results = await manager.check_all_health()
    for item in results:
        item["houses_count"] = db.query(House).filter(
            House.source == item["source"]).count()
        item["probed"] = True
    return {"success": True, "code": 0, "data": results}


@router.get("/sources", response_model=List[SourceStatus])
async def list_sources(db: Session = Depends(get_db)):
    """列出所有数据源状态（只读，不会写入数据库）"""
    configs = db.query(SourceConfig).all()
    config_map = {c.source: c for c in configs}

    result = []
    for source, info in SOURCE_CONFIGS.items():
        config = config_map.get(source)

        # 统计房源数
        count = db.query(House).filter(House.source == source).count()

        result.append(SourceStatus(
            source=source,
            display_name=info["display_name"],
            enabled=config.enabled if config else False,
            status=config.status if config else "pending",
            last_crawl_time=config.last_crawl_time if config else None,
            houses_count=count,
            error_message=config.error_message if config else None,
            needs_login=info["needs_login"],
        ))

    return result


@router.post("/sources/{source}/enable")
async def enable_source(source: str, db: Session = Depends(get_db)):
    """启用数据源（可重复调用）"""
    if source not in CrawlerManager.CRAWLERS and source not in SOURCE_CONFIGS:
        raise HTTPException(status_code=400, detail=f"未知数据源: {source}")

    try:
        config = db.query(SourceConfig).filter(SourceConfig.source == source).first()
        if not config:
            config = SourceConfig(source=source)
            db.add(config)

        config.enabled = True
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"启用失败: {type(e).__name__}: {e}")

    return {"success": True, "code": 0, "message": f"已启用数据源: {source}"}


@router.post("/sources/{source}/disable")
async def disable_source(source: str, db: Session = Depends(get_db)):
    """禁用数据源（可重复调用）"""
    try:
        config = db.query(SourceConfig).filter(SourceConfig.source == source).first()
        if config:
            config.enabled = False
            db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"禁用失败: {type(e).__name__}: {e}")

    return {"success": True, "code": 0, "message": f"已禁用数据源: {source}"}


async def _run_crawl_task(source: str, city: str, keyword: str, pages: int,
                          rent_type: int, with_detail: int):
    """后台执行真实采集（使用独立会话，避免请求级会话提前关闭）"""
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        manager = CrawlerManager(db)
        result = await manager.crawl(
            source, city, keyword, pages,
            rent_type=rent_type, with_detail=with_detail,
        )
        print(f"[crawl] {source} {city} -> {result.get('status')}: {result.get('message')}")
    except Exception as e:
        print(f"[crawl] {source} {city} 失败: {type(e).__name__}: {e}")
    finally:
        db.close()


@router.post("/crawl")
async def trigger_crawl(
    request: CrawlRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """手动触发爬虫（真实执行，后台运行）

    立即返回 running，随后可用 `GET /api/crawl/logs` 查看结果：
    状态会写入 success / empty / needs_login / blocked / unavailable / error，
    便于区分"没有房源"和"被平台拦截"。
    """
    crawler_class = CrawlerManager.CRAWLERS.get(request.source)
    if crawler_class is None:
        raise HTTPException(
            status_code=400,
            detail=f"未知数据源: {request.source}，可用: {list(CrawlerManager.CRAWLERS)}",
        )

    city = request.city or "北京"
    background.add_task(
        _run_crawl_task, request.source, city, request.keyword or "",
        request.pages, request.rent_type, request.with_detail,
    )

    # 更新数据源状态的时间戳
    config = db.query(SourceConfig).filter(SourceConfig.source == request.source).first()
    if config:
        config.last_crawl_time = datetime.now()
        db.commit()

    return {
        "success": True,
        "code": 0,
        "source": request.source,
        "status": "running",
        "message": f"已在后台启动采集: {crawler_class.DISPLAY_NAME} / {city}"
                   f"（结果见 /api/crawl/logs）",
        "houses_count": 0,
    }


@router.get("/crawl/logs")
async def get_crawl_logs(
    source: str = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取爬虫日志"""
    query = db.query(CrawlLog).order_by(CrawlLog.start_time.desc())
    if source:
        query = query.filter(CrawlLog.source == source)

    logs = query.limit(limit).all()
    return {
        "success": True,
        "data": [
            {
                "id": log.id,
                "source": log.source,
                "city": log.city,
                "status": log.status,
                "message": log.message,
                "housesCount": log.houses_count,
                "startTime": log.start_time.isoformat() if log.start_time else None,
                "endTime": log.end_time.isoformat() if log.end_time else None,
            }
            for log in logs
        ]
    }
