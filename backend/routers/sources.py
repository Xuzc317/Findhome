from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.constants import SOURCE_CONFIGS
from backend.database import get_db
from backend.models import SourceConfig, House, CrawlLog
from backend.schemas import SourceStatus, CrawlRequest, CrawlResponse
from datetime import datetime
from typing import List

router = APIRouter()


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
    """启用数据源"""
    config = db.query(SourceConfig).filter(SourceConfig.source == source).first()
    if not config:
        config = SourceConfig(source=source)
        db.add(config)

    config.enabled = True
    db.commit()

    return {"success": True, "message": f"已启用数据源: {source}"}


@router.post("/sources/{source}/disable")
async def disable_source(source: str, db: Session = Depends(get_db)):
    """禁用数据源"""
    config = db.query(SourceConfig).filter(SourceConfig.source == source).first()
    if config:
        config.enabled = False
        db.commit()

    return {"success": True, "message": f"已禁用数据源: {source}"}


@router.post("/crawl", response_model=CrawlResponse)
async def trigger_crawl(request: CrawlRequest, db: Session = Depends(get_db)):
    """手动触发爬虫（实际爬虫实现独立运行）"""
    # 记录日志
    log = CrawlLog(
        source=request.source,
        city=request.city,
        status="running",
        message=f"手动触发: 城市={request.city}, 关键词={request.keyword}",
    )
    db.add(log)
    db.commit()

    # 更新数据源状态
    config = db.query(SourceConfig).filter(SourceConfig.source == request.source).first()
    if config:
        config.last_crawl_time = datetime.now()
        db.commit()

    return CrawlResponse(
        source=request.source,
        status="running",
        message="爬虫任务已启动，请稍后查看结果",
        houses_count=0,
    )


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
