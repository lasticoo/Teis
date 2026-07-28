import logging
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, Response, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.services.backup_service import generate_full_sql_dump

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["Database Backup"])


@router.get("/download")
def download_database_backup(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    """
    Generates a full MySQL .sql dump file of all TEIS tables and data for manual user backup.
    """
    try:
        filename_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sql_content = generate_full_sql_dump(db)
        filename = f"teis_backup_{filename_stamp}.sql"

        return Response(
            content=sql_content,
            media_type="application/sql",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

    except Exception as e:
        logger.error(f"❌ Failed to generate database backup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menggenerasi backup database: {str(e)}"
        )
