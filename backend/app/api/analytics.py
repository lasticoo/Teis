import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.auth import get_current_user
from app.services.equity_service import EquitySnapshotService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/equity-curve")
def get_equity_curve(
    range: str = Query("all", description="Range filter: 7d, 30d, 90d, 1y, month, year, all"),
    start_date: Optional[str] = Query(None, description="ISO Start Date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO End Date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Returns dual-line dataset for Equity Growth Curve:
    1. Real Equity Balance ($)
    2. Cumulative R / Net PnL ($ / R)
    """
    try:
        data = EquitySnapshotService.get_equity_curve(
            db=db,
            range_filter=range,
            start_date=start_date,
            end_date=end_date
        )
        return data
    except Exception as e:
        logger.error(f"Failed to fetch equity curve: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil data kurva ekuitas: {str(e)}"
        )


@router.get("/summary")
def get_analytics_summary(
    filter_source: str = Query("all", description="Source filter: live, import, all"),
    filter_pair: str = Query("all", description="Pair filter: e.g. BTCUSDT or all"),
    filter_session: str = Query("all", description="Session filter: Asia, London, New York or all"),
    start_date: Optional[str] = Query(None, description="ISO Start Date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO End Date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Returns comprehensive Analytics Engine performance summary metrics calculated with Pandas/NumPy.
    """
    try:
        from app.services.analytics_engine import AnalyticsEngine
        summary = AnalyticsEngine.compute_summary(
            db=db,
            filter_source=filter_source,
            filter_pair=filter_pair,
            filter_session=filter_session,
            start_date=start_date,
            end_date=end_date
        )
        return summary
    except Exception as e:
        logger.error(f"Failed to compute analytics summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menghitung ringkasan analitis: {str(e)}"
        )


@router.get("/distribution")
def get_r_distribution(
    filter_source: str = Query("all", description="Source filter: live, import, all"),
    filter_pair: str = Query("all", description="Pair filter: e.g. BTCUSDT or all"),
    filter_session: str = Query("all", description="Session filter: Asia, London, New York or all"),
    start_date: Optional[str] = Query(None, description="ISO Start Date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO End Date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Returns 7-bin histogram frequency distribution for R-multiples.
    """
    try:
        from app.services.analytics_engine import AnalyticsEngine
        distribution = AnalyticsEngine.compute_distribution(
            db=db,
            filter_source=filter_source,
            filter_pair=filter_pair,
            filter_session=filter_session,
            start_date=start_date,
            end_date=end_date
        )
        return {"distribution": distribution}
    except Exception as e:
        logger.error(f"Failed to compute R-distribution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menghitung distribusi R: {str(e)}"
        )
