from sqlalchemy import text
from app.database import SessionLocal
from app.models.models import Trade

db = SessionLocal()
try:
    # 1. Clear locked_at for dummy test trades
    db.execute(text("UPDATE trades SET locked_at = NULL WHERE pair = 'BTCUSDT' AND data_source = 'manual'"))
    db.commit()

    # 2. Delete dummy test trades
    res = db.execute(text("DELETE FROM trades WHERE pair = 'BTCUSDT' AND data_source = 'manual'"))
    db.commit()

    print(f"Successfully cleaned up dummy test trades. Rows affected: {res.rowcount}")
except Exception as e:
    db.rollback()
    print(f"Error cleaning up trades: {e}")
finally:
    db.close()
