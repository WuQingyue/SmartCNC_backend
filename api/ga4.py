# /api/ga4.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from utils.database import get_db
from utils.ga4_client import (
    get_today_stats, 
    get_visitor_data, 
    get_amount_data,
    get_active_users_last_30_minutes,
    get_active_users_last_30_minutes_by_country,
    get_user_source_platform_data,
    get_active_users_by_platform_and_country
)
from typing import Optional

router = APIRouter()

@router.get("/today-stats")
async def today_stats(start_date: Optional[str] = None, end_date: Optional[str] = None, db: Session = Depends(get_db)):
    """
    获取指定日期范围的统计数据。
    如果未提供日期，则默认为今天。
    """
    try:
        # 如果没有提供日期，则使用 None，让后端逻辑决定是否用当天日期
        stats = get_today_stats(start_date, end_date)
        # 注意：当查询历史某一天时，"较昨日"的比较逻辑可能会很复杂或无意义
        # 这里我们统一返回0
        stats["visitorsChange"] = 0
        stats["ordersChange"] = 0
        stats["revenueChange"] = 0
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/visitor-data")
async def visitor_data(start_date: str, end_date: str, db: Session = Depends(get_db)):
    """
    获取指定日期范围的每小时访客数据
    """
    try:
        return get_visitor_data(start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/amount-data")
async def amount_data(start_date: str, end_date: str, db: Session = Depends(get_db)):
    try:
        return get_amount_data(start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active-users-last-30-minutes")
async def active_users_last_30_minutes(db: Session = Depends(get_db)):
    try:
        return get_active_users_last_30_minutes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active-users-last-30-minutes-by-country")
async def active_users_last_30_minutes_by_country(db: Session = Depends(get_db)):
    try:
        return get_active_users_last_30_minutes_by_country()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user-source-platform-data")
async def user_source_platform_data(start_date: str, end_date: str, db: Session = Depends(get_db)):
    try:
        return get_user_source_platform_data(start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 添加新路由
@router.get("/active-users-by-platform-country")
async def active_users_by_platform_country(db: Session = Depends(get_db)):
    """
    获取过去30分钟内按平台和国家/地区细分的活跃用户。
    """
    try:
        return get_active_users_by_platform_and_country()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
