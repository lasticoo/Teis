import logging
from sqlalchemy import text
from app.database import SessionLocal
from app.api.journal import seed_taxonomy_if_empty

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset_trades_data")


def reset_trade_data():
    db = SessionLocal()
    try:
        logger.info("Memulai reset total seluruh data trade di database...")
        
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        tables_to_clear = [
            "trade_fills",
            "trade_setup_tags",
            "psychology",
            "screenshots",
            "market_context",
            "trade_corrections",
            "exchange_fills",
            "trades",
        ]
        
        for table in tables_to_clear:
            db.execute(text(f"TRUNCATE TABLE {table};"))
            logger.info(f"  -> Tabel '{table}' berhasil dikosongkan.")
            
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        db.commit()

        # Re-seed taxonomy choices
        seed_taxonomy_if_empty(db)

        # Clear Redis cache
        try:
            from app.services.redis import redis_client
            redis_client.flushdb()
            logger.info("  -> Cache Redis berhasil dibersihkan.")
        except Exception as e:
            logger.warning(f"  -> Redis flush: {str(e)}")

        logger.info("\n✅ RESET TOTAL DATA TRADE BERHASIL! Akun user, kredensial Binance, dan taksonomi setup tetap aman.")
    except Exception as e:
        logger.error(f"Gagal melakukan reset data: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    reset_trade_data()
