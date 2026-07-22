import sys
import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.database import SessionLocal
from app.models.models import Trade, ExchangeFill, TradeFill
from app.services.binance import BinanceService
from app.services.trade_collection import TradeCollectionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repair_live_trades")


from sqlalchemy import text


def repair_all_trades():
    db = SessionLocal()
    try:
        # Save map of locked_at for all trades and set locked_at to NULL temporarily in DB
        locked_map = {}
        all_trades_raw = db.query(Trade).all()
        for t in all_trades_raw:
            if t.locked_at:
                locked_map[t.id] = t.locked_at
                db.execute(text("UPDATE trades SET locked_at = NULL WHERE id = :tid"), {"tid": t.id})
        db.commit()

        # Re-fetch fresh trade objects with locked_at = NULL
        trades = db.query(Trade).all()
        logger.info(f"Ditemukan {len(trades)} trade di database untuk diperbaiki.")

        pairs = {t.pair for t in trades}
        
        # 1. Fetch raw Binance userTrades for each symbol and populate exchange_fills
        for pair in pairs:
            logger.info(f"Mengambil riwayat fills Binance untuk symbol {pair}...")
            try:
                raw_fills = BinanceService.get_user_trades(db, pair)
                logger.info(f"  -> Diterima {len(raw_fills)} fills dari Binance Futures API.")
                
                for fill in raw_fills:
                    trade_id_binance = int(fill["id"])
                    order_id_binance = int(fill["orderId"])
                    
                    ex_fill = db.query(ExchangeFill).filter(
                        ExchangeFill.symbol == pair,
                        ExchangeFill.binance_trade_id == trade_id_binance
                    ).first()
                    
                    if not ex_fill:
                        ex_fill = ExchangeFill(
                            symbol=pair,
                            binance_trade_id=trade_id_binance,
                            binance_order_id=order_id_binance,
                            price=Decimal(str(fill["price"])),
                            qty=Decimal(str(fill["qty"])),
                            fee=Decimal(str(fill["commission"])),
                            funding_fee=Decimal("0.0"),
                            side=fill["side"].upper(),
                            executed_at=datetime.fromtimestamp(int(fill["time"]) / 1000.0, tz=timezone.utc),
                            raw_payload=fill
                        )
                        db.add(ex_fill)
                        logger.info(f"     [NEW FILL] {pair} {fill['side']} Px={fill['price']} Qty={fill['qty']} ID={trade_id_binance}")
                db.commit()
            except Exception as e:
                logger.error(f"Gagal mengambil fills untuk {pair}: {str(e)}")

        # 2. Re-link fills and recalculate VWAP & financials for each trade
        for trade in trades:
            logger.info(f"\n--- Memperbaiki Trade ID: {trade.id} ({trade.pair} {trade.direction.upper()}) ---")

            # Clean up old mismatched trade_fills for this trade
            db.query(TradeFill).filter(TradeFill.trade_id == trade.id).delete()
            db.commit()

            # Execute auto_match_unlinked_fills and link_trade_fills
            res = TradeCollectionService.link_trade_fills(db, trade.id)
            logger.info(f"Status Linking: {res}")

            # Fetch updated trade record
            updated = db.query(Trade).filter(Trade.id == trade.id).first()
            logger.info(f"Hasil Perbaikan:")
            logger.info(f"  Entry VWAP   : {updated.entry_price}")
            logger.info(f"  Exit VWAP    : {updated.exit_price}")
            logger.info(f"  Entry Time   : {updated.entry_time}")
            logger.info(f"  Exit Time    : {updated.exit_time}")
            logger.info(f"  Holding Time : {updated.holding_time_sec} detik")
            logger.info(f"  Net PnL      : {updated.pnl}")
            logger.info(f"  Fee          : {updated.fee}")
            logger.info(f"  Realized RR  : {updated.rr_realized}R")
            logger.info(f"  Fills Count  : {len(updated.fills)}")

        # Restore original locked_at timestamps
        for tid, loc in locked_map.items():
            db.execute(text("UPDATE trades SET locked_at = :loc WHERE id = :tid"), {"loc": loc, "tid": tid})
        db.commit()

        logger.info("\n✅ PERBAIKAN DATA DENGAN DATA RIIL BINANCE SELESAI!")
    except Exception as e:
        logger.error(f"Error saat perbaikan data: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    repair_all_trades()
