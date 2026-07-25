"""
Celery tasks for Historical Import Wizard (Fitur 9).
Responsibilities:
  - Receive start/end timestamps from API router.
  - Run HistoricalImportService.run_import() in background.
  - Broadcast real-time progress via Redis Pub/Sub → WebSocket manager.
"""
import json
import time
import logging
import uuid
import redis

from app.tasks.worker import celery_app
from app.database import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

# Redis channel used to relay progress events to WebSocket clients
IMPORT_PROGRESS_CHANNEL = "import_progress"


def _publish_progress(redis_client: redis.Redis, job_id: str, payload: dict) -> None:
    """Publish a progress event to Redis so WebSocket manager can relay it."""
    payload["job_id"] = job_id
    try:
        redis_client.publish(IMPORT_PROGRESS_CHANNEL, json.dumps(payload))
    except Exception as e:
        logger.warning(f"[ImportTask] Failed to publish progress to Redis: {e}")


@celery_app.task(name="tasks.import_historical_trades", bind=True, max_retries=0)
def import_historical_trades_task(self, job_id: str, start_ts: int, end_ts: int) -> dict:
    """
    Celery background task that orchestrates the historical import.

    Args:
        job_id: Unique identifier for this import run (for WS correlation).
        start_ts: Start of import range in Unix milliseconds.
        end_ts: End of import range in Unix milliseconds.

    Returns:
        Summary dict with totals.
    """
    logger.info(f"[ImportTask] Starting job {job_id} | {start_ts} → {end_ts}")

    # Connect to Redis for progress publishing
    redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)

    # Emit "started" event
    _publish_progress(redis_client, job_id, {
        "event": "started",
        "pct": 0,
        "fills_found": 0,
        "trades_saved": 0,
        "skipped": 0,
        "current_symbol": None,
        "message": "Import dimulai, menghubungkan ke Binance…",
    })

    db = SessionLocal()
    start_wall = time.time()

    try:
        # Lazy import to avoid circular dependencies
        from app.services.historical_import_service import HistoricalImportService

        def progress_callback(payload: dict) -> None:
            _publish_progress(redis_client, job_id, payload)

        summary = HistoricalImportService.run_import(
            db=db,
            start_ts=start_ts,
            end_ts=end_ts,
            progress_callback=progress_callback,
        )

        duration = round(time.time() - start_wall, 1)

        # Emit completion event
        _publish_progress(redis_client, job_id, {
            "event": "complete",
            "pct": 100,
            "fills_found": summary["total_fills"],
            "trades_saved": summary["total_trades"],
            "skipped": summary["total_skipped"],
            "current_symbol": None,
            "message": (
                f"✅ Import selesai dalam {duration}s — "
                f"{summary['total_trades']} trade, "
                f"{summary['total_fills']} fill, "
                f"{summary['total_skipped']} dilewati (duplikat)."
            ),
            "duration_seconds": duration,
        })

        logger.info(f"[ImportTask] Job {job_id} complete: {summary}")
        return {**summary, "job_id": job_id, "duration_seconds": duration}

    except Exception as exc:
        logger.exception(f"[ImportTask] Job {job_id} failed: {exc}")
        _publish_progress(redis_client, job_id, {
            "event": "error",
            "pct": 0,
            "fills_found": 0,
            "trades_saved": 0,
            "skipped": 0,
            "current_symbol": None,
            "message": f"❌ Import gagal: {str(exc)}",
        })
        raise

    finally:
        db.close()
        redis_client.close()
