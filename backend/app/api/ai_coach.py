from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AICoachReview, Trade
from app.services.ai_coach_service import AICoachService

router = APIRouter(prefix="/ai-coach", tags=["AI Coach Service"])


class AICoachRequest(BaseModel):
    trade_id: str = Field(..., description="Valid UUID of the closed trade to evaluate")


@router.post("/review")
def request_ai_coach_review(
    payload: AICoachRequest,
    db: Session = Depends(get_db)
):
    """
    FITUR 14 - POST /api/v1/ai-coach/review
    Triggers post-trade AI evaluation. Anonymizes account details, gathers historical setup metrics,
    and returns qualitative AI coaching feedback.
    """
    try:
        review = AICoachService.generate_trade_review(db, payload.trade_id)
        return review
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Layanan AI Coach gagal memproses evaluasi: {str(e)}"
        )


@router.get("/review/{trade_id}")
def get_existing_ai_coach_review(
    trade_id: str,
    db: Session = Depends(get_db)
):
    """
    FITUR 14 - GET /api/v1/ai-coach/review/{trade_id}
    Fetches stored AI Coach qualitative review for a specific trade.
    """
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade dengan ID '{trade_id}' tidak ditemukan."
        )

    review_record = db.query(AICoachReview).filter(AICoachReview.trade_id == trade_id).first()
    review_text = review_record.feedback_markdown if review_record else None

    return {
        "trade_id": trade_id,
        "pair": trade.pair,
        "ai_coach_review": review_text,
        "has_review": review_text is not None
    }
