import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from celery import Celery
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal
from app.models.models import Trade, ExchangeFill, TradeFill, APICredential
from app.services.binance import BinanceService

logger = logging.getLogger(__name__)

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

# Polling beat schedule: run poll_open_positions every 30 seconds
celery_app.conf.beat_schedule = {
    "poll_open_positions_every_30s": {
        "task": "tasks.poll_open_positions",
        "schedule": 30.0,
    }
}

@celery_app.task(name="tasks.poll_open_positions")
def poll_open_positions():
    logger.info("Starting periodic poll_open_positions task...")
    db = SessionLocal()
    try:
        # Check if Binance credentials exist
        cred = db.query(APICredential).filter(APICredential.service_name == "binance").first()
        if not cred:
            logger.info("Binance API credentials not configured yet. Skipping poll.")
            return "skipped"

        # Fetch position risk from Binance
        try:
            positions = BinanceService.get_position_risk(db)
        except Exception as e:
            logger.error(f"Failed to fetch position risk from Binance: {str(e)}")
            return "failed_api"

        # Filter active positions (positionAmt != 0)
        active_pos_map = {}
        for pos in positions:
            symbol = pos["symbol"]
            amt = float(pos["positionAmt"])
            if amt != 0.0:
                active_pos_map[symbol] = pos

        # Fetch active trades (exit_time is NULL) from DB
        active_trades = db.query(Trade).filter(
            Trade.exit_time == None,
            Trade.data_source == 'binance_sync'
        ).all()
        active_trades_map = {t.pair: t for t in active_trades}

        # 1. Process Open Positions
        for symbol, pos in active_pos_map.items():
            pos_amt = Decimal(pos["positionAmt"])
            leverage_val = pos.get("leverage")
            leverage = Decimal(str(leverage_val)) if leverage_val is not None else None
            entry_price_binance = Decimal(pos["entryPrice"])
            update_time = datetime.fromtimestamp(int(pos["updateTime"]) / 1000.0, tz=timezone.utc)

            # Check if this position is already tracked
            if symbol in active_trades_map:
                # Update SL/TP if changed in Binance
                trade = active_trades_map[symbol]
                try:
                    update_sl_tp(db, trade)
                except Exception as e:
                    logger.error(f"Failed to update SL/TP for active trade {trade.id}: {str(e)}")
                continue

            # Position is new -> Create Trade shell and link entry fills
            logger.info(f"New active position detected for {symbol}. Creating trade shell...")
            
            direction = "long" if pos_amt > 0 else "short"
            margin = (abs(pos_amt) * entry_price_binance / leverage) if leverage else None

            trade = Trade(
                pair=symbol,
                direction=direction,
                entry_price=entry_price_binance,
                entry_time=update_time,
                margin=margin,
                leverage=leverage,
                risk_amount=Decimal("0.0"),  # Default risk (can be set during tag)
                data_source="binance_sync"
            )
            db.add(trade)
            db.flush()

            # Retrieve entry fills from last 15 minutes
            try:
                start_ts = int(pos["updateTime"]) - 900000  # 15 minutes ago
                fills = BinanceService.get_user_trades(db, symbol, start_time=start_ts)
                process_fills(db, trade, fills, role="entry")
            except Exception as e:
                logger.error(f"Failed to retrieve entry fills for new trade {trade.id}: {str(e)}")

            # Check Stop Loss / Take Profit
            try:
                update_sl_tp(db, trade)
            except Exception as e:
                logger.error(f"Failed to fetch SL/TP orders for trade {trade.id}: {str(e)}")

            # Trigger notification banner mock (will be fully implemented in Fitur 8)
            trigger_notification(db, trade, "trade_pending_tag")
            db.commit()

        # 2. Process Closed Positions
        for pair, trade in active_trades_map.items():
            if pair not in active_pos_map:
                # Position has been closed!
                logger.info(f"Active position for {pair} is no longer open. Closing trade journal record...")
                
                # Fetch recent trades to find exit fills
                try:
                    start_ts = int(trade.entry_time.timestamp() * 1000) - 60000  # 1 minute before entry
                    fills = BinanceService.get_user_trades(db, pair, start_time=start_ts)
                    exit_fills = process_fills(db, trade, fills, role="exit")
                    
                    if exit_fills:
                        # Calculate financial aggregates
                        total_exit_qty = sum(f.qty for f in exit_fills)
                        weighted_exit_price = sum(f.price * f.qty for f in exit_fills) / total_exit_qty if total_exit_qty > 0 else trade.entry_price
                        
                        trade.exit_price = weighted_exit_price
                        trade.exit_time = max(f.executed_at for f in exit_fills)
                        
                        # Total realized PnL from exit fills
                        trade.pnl = sum((Decimal(str(f.raw_payload.get("realizedPnl", "0.0"))) for f in exit_fills), Decimal("0.0"))
                        
                        # Total fee from all linked fills (entry & exit)
                        all_fills = db.query(ExchangeFill).join(TradeFill).filter(TradeFill.trade_id == trade.id).all()
                        trade.fee = sum((f.fee for f in all_fills), Decimal("0.0"))
                        
                        # Realized Risk-to-Reward (RR)
                        if trade.risk_amount and trade.risk_amount > 0:
                            trade.rr_realized = (trade.pnl - trade.fee) / trade.risk_amount
                        else:
                            trade.rr_realized = Decimal("0.0")
                            
                    else:
                        # Fallback if no exit fills found
                        trade.exit_price = trade.entry_price
                        trade.exit_time = datetime.now(timezone.utc)
                        trade.pnl = Decimal("0.0")
                        trade.fee = Decimal("0.0")
                        trade.rr_realized = Decimal("0.0")
                        
                except Exception as e:
                    logger.error(f"Failed to process exit fills for trade {trade.id}: {str(e)}")
                    # Fallback on exception
                    trade.exit_price = trade.entry_price
                    trade.exit_time = datetime.now(timezone.utc)

                db.commit()
                
                # Trigger asynchronous task to collect market context
                logger.info(f"Triggering market context collection for trade {trade.id}...")
                collect_market_context.delay(trade.id)

        return "success"
    except Exception as e:
        logger.error(f"Unexpected error in poll_open_positions: {str(e)}")
        db.rollback()
        return "error"
    finally:
        db.close()

def update_sl_tp(db: Session, trade: Trade):
    # Fetch active orders to identify SL/TP levels
    orders = BinanceService.get_open_orders(db, trade.pair)
    for order in orders:
        orig_type = order.get("type", "").upper()
        stop_price = Decimal(order.get("stopPrice", "0"))
        
        # Stop loss detection
        if orig_type in ["STOP", "STOP_MARKET"] and stop_price > 0:
            trade.stop_loss = stop_price
            
        # Take profit detection
        elif orig_type in ["TAKE_PROFIT", "TAKE_PROFIT_MARKET"] and stop_price > 0:
            trade.take_profit = stop_price

def process_fills(db: Session, trade: Trade, fills, role: str):
    processed = []
    # Determine the side of the fill depending on trade direction and role
    # Entry: long position starts with BUY fills, short starts with SELL fills
    # Exit: long position closes with SELL fills, short closes with BUY fills
    target_side = ""
    if role == "entry":
        target_side = "BUY" if trade.direction == "long" else "SELL"
    else:
        target_side = "SELL" if trade.direction == "long" else "BUY"

    for fill in fills:
        if fill.get("side", "").upper() != target_side:
            continue
            
        trade_id_binance = int(fill["id"])
        order_id_binance = int(fill["orderId"])
        
        # Avoid duplicate fills using UniqueConstraint
        ex_fill = db.query(ExchangeFill).filter(
            ExchangeFill.symbol == trade.pair,
            ExchangeFill.binance_trade_id == trade_id_binance
        ).first()
        
        if not ex_fill:
            ex_fill = ExchangeFill(
                symbol=trade.pair,
                binance_trade_id=trade_id_binance,
                binance_order_id=order_id_binance,
                price=Decimal(str(fill["price"])),
                qty=Decimal(str(fill["qty"])),
                fee=Decimal(str(fill["commission"])),
                funding_fee=Decimal("0.0"),  # Funding fee can be calculated in Fitur 10
                side=fill["side"].upper(),
                executed_at=datetime.fromtimestamp(int(fill["time"]) / 1000.0, tz=timezone.utc),
                raw_payload=fill
            )
            db.add(ex_fill)
            db.flush()

        # Link fill to trade using TradeFill helper
        link = db.query(TradeFill).filter(
            TradeFill.trade_id == trade.id,
            TradeFill.exchange_fill_id == ex_fill.id
        ).first()
        
        if not link:
            link = TradeFill(
                trade_id=trade.id,
                exchange_fill_id=ex_fill.id,
                role=role
            )
            db.add(link)
            db.flush()
            
        processed.append(ex_fill)
        
    return processed

def trigger_notification(db: Session, trade: Trade, notif_type: str):
    # Log notifications (stubs, will be integrated with Multi-Channel notifications)
    logger.info(f"NOTIFICATION STUB: Triggered '{notif_type}' alert for trade {trade.id} ({trade.pair})")

@celery_app.task(name="tasks.collect_market_context")
def collect_market_context(trade_id: str):
    logger.info(f"Mock collecting market context for trade {trade_id}...")
    return {"status": "success", "trade_id": trade_id}

@celery_app.task(name="tasks.discover_edges")
def discover_edges():
    logger.info("Running edge discovery process...")
    return {"status": "success", "edges_discovered": 0}
