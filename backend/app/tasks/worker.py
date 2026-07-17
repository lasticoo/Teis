from celery import Celery
from app.config import settings

# Initialize Celery app
celery_app = Celery(
    "teis_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,
)

# Example task placeholder
@celery_app.task(name="tasks.sync_binance_trades")
def sync_binance_trades(pair: str):
    print(f"Syncing trades for {pair}...")
    return {"status": "success", "pair": pair}

@celery_app.task(name="tasks.collect_market_context")
def collect_market_context(trade_id: str):
    print(f"Collecting market context for trade {trade_id}...")
    return {"status": "success", "trade_id": trade_id}

@celery_app.task(name="tasks.discover_edges")
def discover_edges():
    print("Running edge discovery process...")
    return {"status": "success", "edges_discovered": 0}
