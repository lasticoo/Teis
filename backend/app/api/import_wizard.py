"""
FastAPI Router for Historical Import Wizard (Fitur 9).
Follows SOLID:
  - S: Only handles HTTP + WebSocket concerns; delegates business logic to tasks/service.
  - O: New import sources can be added as new endpoints without modifying existing ones.
  - D: Depends on Celery task abstraction, not concrete service.
"""
import json
import uuid
import asyncio
import logging
import redis.asyncio as aioredis

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.models import User
from app.schemas.import_schema import ImportRequest, ImportJobResponse
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import", tags=["Historical Import"])

# Redis channel must match the one in import_tasks.py
IMPORT_PROGRESS_CHANNEL = "import_progress"


# ---------------------------------------------------------------------------
# POST /api/v1/import/binance — Trigger import job
# ---------------------------------------------------------------------------
@router.post("/binance", response_model=ImportJobResponse, status_code=status.HTTP_202_ACCEPTED)
def start_historical_import(
    payload: ImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validates date range and dispatches a Celery background task to
    pull historical Binance Futures trade fills.
    Returns a job_id for WebSocket progress tracking.
    """
    # Convert dates to millisecond timestamps
    start_ts = int(
        datetime(payload.start_date.year, payload.start_date.month, payload.start_date.day,
                 tzinfo=timezone.utc).timestamp() * 1000
    )
    end_ts = int(
        datetime(payload.end_date.year, payload.end_date.month, payload.end_date.day,
                 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000
    )

    job_id = str(uuid.uuid4())

    try:
        from app.tasks.import_tasks import import_historical_trades_task
        import_historical_trades_task.apply_async(
            args=[job_id, start_ts, end_ts],
            task_id=job_id,
        )
    except Exception as e:
        logger.error(f"[ImportRouter] Failed to dispatch Celery task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memulai import: {str(e)}",
        )

    logger.info(f"[ImportRouter] Job {job_id} dispatched for user {current_user.username}")
    return ImportJobResponse(
        job_id=job_id,
        status="queued",
        message="Import historis sedang diproses di background. Monitor via WebSocket.",
        start_date=str(payload.start_date),
        end_date=str(payload.end_date),
    )


# ---------------------------------------------------------------------------
# WebSocket /api/v1/import/ws/{job_id} — Real-time progress stream
# ---------------------------------------------------------------------------
@router.websocket("/ws/{job_id}")
async def import_progress_ws(
    websocket: WebSocket,
    job_id: str,
):
    """
    WebSocket endpoint that subscribes to Redis Pub/Sub channel and relays
    progress events for the specified job_id to the connected browser client.
    Auto-closes when a 'complete' or 'error' event is received.
    """
    await websocket.accept()
    logger.info(f"[ImportWS] Client connected for job {job_id}")

    redis_client = aioredis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(IMPORT_PROGRESS_CHANNEL)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            # Only relay events belonging to this job
            if data.get("job_id") != job_id:
                continue

            await websocket.send_json(data)

            # Close when job finishes
            if data.get("event") in ("complete", "error"):
                logger.info(f"[ImportWS] Job {job_id} finished, closing WebSocket.")
                break

    except WebSocketDisconnect:
        logger.info(f"[ImportWS] Client disconnected for job {job_id}")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"[ImportWS] Unexpected error for job {job_id}: {e}")
    finally:
        await pubsub.unsubscribe(IMPORT_PROGRESS_CHANNEL)
        await redis_client.aclose()
        try:
            await websocket.close()
        except Exception:
            pass
