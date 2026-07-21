from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, Trade

router = APIRouter(prefix="/trades", tags=["Trades"])

@router.get("/pending-count")
def get_pending_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Active/pending trade shells have exit_time as None
    count = db.query(Trade).filter(Trade.exit_time == None).count()
    return {"count": count}
