import json
import logging
import redis
import requests
import pandas as pd
from datetime import datetime, timezone
from decimal import Decimal
from celery import Celery
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal
from app.models.models import Trade, ExchangeFill, TradeFill, APICredential, MarketContext
from app.services.binance import BinanceService
from app.services.trade_collection import TradeCollectionService
from app.services.edge_discovery_engine import EdgeDiscoveryEngine
from app.services.edge_status_monitor import EdgeStatusMonitor

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
    imports=("app.tasks.notification_tasks", "app.tasks.import_tasks")
)


from celery.schedules import crontab
from app.services.equity_service import EquitySnapshotService

# Polling beat schedule
celery_app.conf.beat_schedule = {
    "poll_open_positions_every_3s": {
        "task": "tasks.poll_open_positions",
        "schedule": 3.0,
    },
    "capture_equity_snapshot_hourly": {
        "task": "tasks.capture_equity_snapshot",
        "schedule": crontab(minute=0),
    },
    "detect_account_transfers_periodically": {
        "task": "tasks.detect_account_transfers",
        "schedule": crontab(minute=15, hour="*/4"),
    },
    "run_edge_discovery_daily": {
        "task": "tasks.run_edge_discovery_engine",
        "schedule": crontab(minute=0, hour=2),  # Every day at 02:00 AM WIB
    },
    "monitor_edge_status_daily": {
        "task": "tasks.monitor_edge_status",
        "schedule": crontab(minute=30, hour=2),  # Every day at 02:30 AM WIB
    },
    "run_daily_backup_daily": {
        "task": "tasks.run_daily_backup",
        "schedule": crontab(minute=0, hour=3),  # Every day at 03:00 AM WIB
    },
    "run_weekly_export_weekly": {
        "task": "tasks.run_weekly_export",
        "schedule": crontab(minute=0, hour=3, day_of_week='sun'),  # Every Sunday at 03:00 AM WIB
    },
    "remind_restore_drill_monthly": {
        "task": "tasks.remind_restore_drill",
        "schedule": crontab(minute=0, hour=9, day_of_month='1'),  # 1st of every month at 09:00 AM WIB
    }
}

@celery_app.task(name="tasks.run_edge_discovery_engine")
def run_edge_discovery_engine():
    logger.info("Starting Celery task run_edge_discovery_engine...")
    db = SessionLocal()
    try:
        res = EdgeDiscoveryEngine.run_discovery(db)
        logger.info(f"Finished run_edge_discovery_engine task: {res}")
        return res
    except Exception as e:
        logger.error(f"Error in run_edge_discovery_engine task: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.monitor_edge_status")
def monitor_edge_status():
    logger.info("Starting Celery task monitor_edge_status...")
    db = SessionLocal()
    try:
        res = EdgeStatusMonitor.evaluate_all_edge_statuses(db)
        logger.info(f"Finished monitor_edge_status task: {res}")
        return res
    except Exception as e:
        logger.error(f"Error in monitor_edge_status task: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

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
            direction = "long" if pos_amt > 0 else "short"
            margin = (abs(pos_amt) * entry_price_binance / leverage) if (leverage and leverage > 0) else None

            # Check if this position is already tracked
            if symbol in active_trades_map:
                # Update SL/TP and live parameters if changed in Binance
                trade = active_trades_map[symbol]
                try:
                    # Update leverage / margin if present
                    if leverage:
                        trade.leverage = leverage
                    if margin:
                        trade.margin = margin
                    update_sl_tp(db, trade)
                    db.commit()
                except Exception as e:
                    logger.error(f"Failed to update SL/TP for active trade {trade.id}: {str(e)}")
                    db.rollback()
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

            # Trigger multi-channel notification (In-App, Web Push, Email)
            try:
                from app.services.notification_service import NotificationService
                NotificationService.send_multi_channel_notification(
                    db=db,
                    notification_type="trade_pending_tag",
                    message=f"⚡ Trade baru terdeteksi di Binance Futures ({symbol} {direction.upper()})! Silakan lakukan Quick-Tag untuk mencatat jurnal Anda.",
                    reference_id=str(trade.id)
                )
            except Exception as e:
                logger.error(f"Failed to send notification for new trade {trade.id}: {str(e)}")
            db.commit()


        # 2. Process Closed Positions
        for pair, trade in active_trades_map.items():
            if pair not in active_pos_map:
                # Position has been closed!
                logger.info(f"Active position for {pair} is no longer open. Closing trade journal record...")
                
                # Fetch recent trades to find exit fills
                try:
                    entry_utc = trade.entry_time.replace(tzinfo=timezone.utc) if trade.entry_time.tzinfo is None else trade.entry_time
                    start_ts = int(entry_utc.timestamp() * 1000) - 60000  # 1 minute before entry
                    fills = BinanceService.get_user_trades(db, pair, start_time=start_ts)
                    process_fills(db, trade, fills, role="exit")
                    
                    # Delegate VWAP, Net PnL, Fee, and Realized RR calculations to TradeCollectionService
                    TradeCollectionService.link_trade_fills(db, trade.id)
                except Exception as e:
                    logger.error(f"Failed to process exit fills for trade {trade.id}: {str(e)}")
                    if not trade.exit_price:
                        trade.exit_price = trade.entry_price
                    if not trade.exit_time:
                        trade.exit_time = datetime.now(timezone.utc)

                # Ensure exit_time is explicitly set if missing
                if trade.exit_time is None:
                    trade.exit_time = datetime.now(timezone.utc)

                db.commit()

                # Trigger multi-channel notification for closed trade
                try:
                    from app.services.notification_service import NotificationService
                    NotificationService.send_multi_channel_notification(
                        db=db,
                        notification_type="trade_closed",
                        message=f"📊 Posisi {pair} telah ditutup di Binance. PnL & Realized RR telah dihitung. Periksa Jurnal Trade Anda.",
                        reference_id=str(trade.id)
                    )
                except Exception as e:
                    logger.error(f"Failed to send close notification for trade {trade.id}: {str(e)}")

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
    orders_data = BinanceService.get_open_orders(db, trade.pair)
    
    sl_types = ["STOP", "STOP_MARKET", "STOP_LOSS", "STOP_LOSS_LIMIT", "TRAILING_STOP_MARKET"]
    tp_types = ["TAKE_PROFIT", "TAKE_PROFIT_MARKET", "TAKE_PROFIT_LIMIT"]

    # 1. Process basic open orders
    for order in orders_data.get("basic", []):
        orig_type = order.get("type", "").upper()
        stop_p = Decimal(str(order.get("stopPrice", "0")))
        p = Decimal(str(order.get("price", "0")))
        trigger_price = stop_p if stop_p > 0 else p
        
        if orig_type in sl_types and trigger_price > 0:
            trade.stop_loss = trigger_price
        elif orig_type in tp_types and trigger_price > 0:
            trade.take_profit = trigger_price

    # 2. Process conditional algo open orders
    for order in orders_data.get("algo", []):
        order_type = order.get("orderType", "").upper()
        trigger_price = Decimal(str(order.get("triggerPrice", "0")))
        
        if order_type in sl_types and trigger_price > 0:
            trade.stop_loss = trigger_price
        elif order_type in tp_types and trigger_price > 0:
            trade.take_profit = trigger_price

    # 3. Calculate planned RR and risk_amount if entry and SL exist
    if trade.stop_loss and trade.entry_price:
        sl = float(trade.stop_loss)
        entry_p = float(trade.entry_price)
        risk_dist = abs(entry_p - sl)

        # Calculate entry quantity from linked entry fills
        entry_tf = db.query(TradeFill).filter(TradeFill.trade_id == trade.id, TradeFill.role == "entry").all()
        entry_qty = sum((float(tf.exchange_fill.qty) for tf in entry_tf if tf.exchange_fill), 0.0)

        if risk_dist > 0 and entry_qty > 0:
            trade.risk_amount = Decimal(str(round(risk_dist * entry_qty, 4)))
        elif trade.margin and float(trade.margin) > 0:
            trade.risk_amount = Decimal(str(trade.margin))
        else:
            trade.risk_amount = Decimal("1.00")

        if trade.take_profit:
            tp = float(trade.take_profit)
            reward_dist = abs(tp - entry_p)
            if risk_dist > 0:
                trade.rr_planned = Decimal(str(round(reward_dist / risk_dist, 2)))

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
            try:
                ex_fill = ExchangeFill(
                    symbol=trade.pair,
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
                db.flush()
            except Exception:
                db.rollback()
                ex_fill = db.query(ExchangeFill).filter(
                    ExchangeFill.symbol == trade.pair,
                    ExchangeFill.binance_trade_id == trade_id_binance
                ).first()

        if ex_fill:
            # Link fill to trade using TradeFill helper
            link = db.query(TradeFill).filter(
                TradeFill.trade_id == trade.id,
                TradeFill.exchange_fill_id == ex_fill.id
            ).first()
            
            if not link:
                try:
                    link = TradeFill(
                        trade_id=trade.id,
                        exchange_fill_id=ex_fill.id,
                        role=role
                    )
                    db.add(link)
                    db.flush()
                except Exception:
                    db.rollback()
                
            processed.append(ex_fill)
            
    return processed

def trigger_notification(db: Session, trade: Trade, notif_type: str):
    from app.services.notification_service import NotificationService
    msg = f"Trade baru terdeteksi: {trade.pair} ({trade.direction.upper()}). Silakan lakukan Quick-Tag sekarang!"
    try:
        NotificationService.send_multi_channel_notification(
            db=db,
            notification_type=notif_type,
            message=msg,
            reference_id=trade.id
        )
    except Exception as e:
        logger.error(f"Failed to trigger multi-channel notification for trade {trade.id}: {str(e)}")

@celery_app.task(name="tasks.collect_market_context")
def collect_market_context(trade_id: str):
    logger.info(f"Starting market context collection for trade {trade_id}...")
    db = SessionLocal()
    try:
        # 1. Fetch trade
        trade = db.query(Trade).filter(Trade.id == trade_id).first()
        if not trade:
            logger.error(f"Trade {trade_id} not found for market context collection.")
            return "failed_not_found"

        # 2. Check if already has market context
        existing_ctx = db.query(MarketContext).filter(MarketContext.trade_id == trade_id).first()
        if existing_ctx and existing_ctx.trend_htf is not None:
            logger.info(f"Market context for trade {trade_id} already collected.")
            return "skipped_already_exists"

        # 3. Get Binance client
        client = BinanceService.get_client(db)

        # 4. Fetch klines
        try:
            klines_1h = client.futures_klines(symbol=trade.pair, interval="1h", limit=100)
            klines_4h = client.futures_klines(symbol=trade.pair, interval="4h", limit=100)
        except Exception as e:
            logger.error(f"Failed to fetch klines from Binance: {str(e)}")
            klines_1h = []
            klines_4h = []

        # 5. Calculate EMA50 and Trend
        trend_ltf = "range"
        trend_htf = "range"
        
        def calculate_ema_trend(klines):
            if len(klines) < 53:
                return "range"
            try:
                closes = [float(k[4]) for k in klines]
                df = pd.DataFrame(closes, columns=["close"])
                df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
                
                last_close = closes[-1]
                ema_last = df["ema50"].iloc[-1]
                ema_prev1 = df["ema50"].iloc[-2]
                ema_prev2 = df["ema50"].iloc[-3]
                
                slope_up = ema_last > ema_prev1 > ema_prev2
                slope_down = ema_last < ema_prev1 < ema_prev2
                
                if last_close > ema_last and slope_up:
                    return "bull"
                elif last_close < ema_last and slope_down:
                    return "bear"
                else:
                    return "range"
            except Exception as e:
                logger.error(f"Error calculating EMA trend: {str(e)}")
                return "range"

        trend_ltf = calculate_ema_trend(klines_1h)
        trend_htf = calculate_ema_trend(klines_4h)

        # 6. Calculate ATR-14 using 1H klines
        atr_val = None
        if len(klines_1h) >= 15:
            try:
                highs = pd.Series([float(k[2]) for k in klines_1h])
                lows = pd.Series([float(k[3]) for k in klines_1h])
                closes = pd.Series([float(k[4]) for k in klines_1h])
                
                tr1 = highs - lows
                tr2 = (highs - closes.shift(1)).abs()
                tr3 = (lows - closes.shift(1)).abs()
                
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr_series = tr.rolling(window=14).mean()
                atr_val = Decimal(str(round(atr_series.iloc[-1], 8)))
            except Exception as e:
                logger.error(f"Error calculating ATR: {str(e)}")

        # 7. Fetch 24h volume from ticker
        volume_24h_val = None
        try:
            ticker = client.futures_ticker(symbol=trade.pair)
            quote_volume = ticker.get("quoteVolume", "0")
            volume_24h_val = Decimal(quote_volume)
        except Exception as e:
            logger.error(f"Failed to fetch volume from Binance: {str(e)}")

        # 8. Fetch Open Interest
        open_interest_val = None
        try:
            oi_data = client.futures_open_interest_hist(symbol=trade.pair, period="5m", limit=1)
            if oi_data:
                open_interest_val = Decimal(oi_data[-1].get("sumOpenInterestValue", "0"))
        except Exception as e:
            logger.error(f"Failed to fetch open interest: {str(e)}")

        # 9. Fetch Funding Rate
        funding_rate_val = None
        try:
            fr_data = client.futures_funding_rate(symbol=trade.pair, limit=1)
            if fr_data:
                funding_rate_val = Decimal(fr_data[-1].get("fundingRate", "0"))
        except Exception as e:
            logger.error(f"Failed to fetch funding rate: {str(e)}")

        # 10. Fetch external macro metrics from Redis cache (or APIs)
        btc_dom_val = Decimal("55.0")
        fgi_val = 50
        
        try:
            r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            r = None

        # BTC Dominance
        btc_dom_cached = r.get("btc_dominance") if r else None
        if btc_dom_cached:
            btc_dom_val = Decimal(btc_dom_cached.decode("utf-8"))
        else:
            try:
                res = requests.get("https://api.coingecko.com/api/v3/global", timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    dom = data.get("data", {}).get("market_cap_percentage", {}).get("btc", 55.0)
                    btc_dom_val = Decimal(str(dom))
                    if r:
                        r.setex("btc_dominance", 3600, str(dom))
            except Exception as e:
                logger.error(f"Failed to fetch BTC Dominance from CoinGecko: {str(e)}")

        # Fear & Greed Index
        fgi_cached = r.get("fear_greed_index") if r else None
        if fgi_cached:
            fgi_val = int(fgi_cached.decode("utf-8"))
        else:
            try:
                res = requests.get("https://api.alternative.me/fng/", timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    val = int(data.get("data", [{}])[0].get("value", 50))
                    fgi_val = val
                    if r:
                        r.setex("fear_greed_index", 3600, str(val))
            except Exception as e:
                logger.error(f"Failed to fetch Fear & Greed Index: {str(e)}")

        # 11. Save/Update Context in MySQL
        def determine_session_from_time(dt):
            utc_hour = dt.hour
            if 0 <= utc_hour < 8:
                return "asia"
            elif 8 <= utc_hour < 16:
                return "london"
            else:
                return "new_york"

        session_name = determine_session_from_time(trade.entry_time)

        if existing_ctx:
            existing_ctx.trend_htf = trend_htf
            existing_ctx.trend_ltf = trend_ltf
            existing_ctx.atr = atr_val
            existing_ctx.volume_24h = volume_24h_val
            existing_ctx.btc_dominance = btc_dom_val
            existing_ctx.fear_greed_index = fgi_val
            existing_ctx.funding_rate = funding_rate_val
            existing_ctx.open_interest = open_interest_val
            existing_ctx.captured_at = datetime.now()
            if not existing_ctx.session:
                existing_ctx.session = session_name
        else:
            new_ctx = MarketContext(
                trade_id=trade_id,
                trend_htf=trend_htf,
                trend_ltf=trend_ltf,
                atr=atr_val,
                volume_24h=volume_24h_val,
                session=session_name,
                btc_dominance=btc_dom_val,
                fear_greed_index=fgi_val,
                funding_rate=funding_rate_val,
                open_interest=open_interest_val,
                captured_at=datetime.now()
            )
            db.add(new_ctx)

        db.commit()
        logger.info(f"Successfully collected market context for trade {trade_id}.")
        return "success"

    except Exception as e:
        logger.error(f"Exception during market context collection for trade {trade_id}: {str(e)}")
        db.rollback()
        return "failed_exception"
    finally:
        db.close()

@celery_app.task(name="tasks.discover_edges")
def discover_edges():
    logger.info("Running edge discovery process...")
    return {"status": "success", "edges_discovered": 0}

@celery_app.task(name="tasks.lock_trade")
def lock_trade(trade_id: str):
    logger.info(f"Starting lock_trade task for trade {trade_id}...")
    db = SessionLocal()
    try:
        trade = db.query(Trade).filter(Trade.id == trade_id).first()
        if trade:
            if trade.locked_at is None:
                trade.locked_at = datetime.now()
                db.commit()
                logger.info(f"Trade {trade_id} has been permanently locked.")
            else:
                logger.info(f"Trade {trade_id} was already locked at {trade.locked_at}.")
        else:
            logger.error(f"Trade {trade_id} not found to lock.")
    except Exception as e:
        logger.error(f"Error locking trade {trade_id}: {str(e)}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="tasks.link_trade_fills")
def link_trade_fills_task(trade_id: str):
    logger.info(f"Starting Celery task link_trade_fills for trade {trade_id}...")
    db = SessionLocal()
    try:
        res = TradeCollectionService.link_trade_fills(db, trade_id)
        return res
    except Exception as e:
        logger.error(f"Error in link_trade_fills task for trade {trade_id}: {str(e)}")
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.capture_equity_snapshot")
def capture_equity_snapshot_task():
    logger.info("Executing periodic capture_equity_snapshot task...")
    db = SessionLocal()
    try:
        snap = EquitySnapshotService.capture_snapshot(db)
        return {"status": "success", "balance": float(snap.balance) if snap else None}
    except Exception as e:
        logger.error(f"Error in capture_equity_snapshot task: {str(e)}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.detect_account_transfers")
def detect_account_transfers_task():
    logger.info("Executing periodic detect_account_transfers task...")
    db = SessionLocal()
    try:
        count = EquitySnapshotService.detect_transfers(db)
        return {"status": "success", "new_transfers": count}
    except Exception as e:
        logger.error(f"Error in detect_account_transfers task: {str(e)}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


from app.services.backup_service import BackupService

@celery_app.task(name="tasks.run_daily_backup")
def run_daily_backup_task():
    logger.info("Executing periodic run_daily_backup task...")
    db = SessionLocal()
    try:
        rec = BackupService.run_daily_backup(db)
        deleted = BackupService.cleanup_old_backups(db, days=30)
        return {"status": rec.status, "backup_id": rec.id, "cleaned_files": deleted}
    except Exception as e:
        logger.error(f"Error in run_daily_backup task: {str(e)}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.run_weekly_export")
def run_weekly_export_task():
    logger.info("Executing periodic run_weekly_export task...")
    db = SessionLocal()
    try:
        rec = BackupService.run_weekly_export(db)
        return {"status": rec.status, "export_id": rec.id}
    except Exception as e:
        logger.error(f"Error in run_weekly_export task: {str(e)}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.remind_restore_drill")
def remind_restore_drill_task():
    logger.info("Executing periodic remind_restore_drill task...")
    db = SessionLocal()
    try:
        notif = BackupService.remind_restore_drill(db)
        return {"status": "success", "notification_sent": bool(notif)}
    except Exception as e:
        logger.error(f"Error in remind_restore_drill task: {str(e)}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.capture_mfe_mae")
def capture_mfe_mae_task(trade_id: str):
    """
    Background task to fetch 1-minute klines from Binance between entry_time and exit_time,
    calculating exact MFE and MAE prices for accurate price-action robustness evaluation.
    """
    logger.info(f"Executing capture_mfe_mae task for trade {trade_id}...")
    db = SessionLocal()
    try:
        trade = db.query(Trade).filter(Trade.id == trade_id).first()
        if not trade or not trade.entry_time or not trade.exit_time:
            return {"status": "skipped", "reason": "Trade or exit_time missing"}

        start_ts = int(trade.entry_time.timestamp() * 1000)
        end_ts = int(trade.exit_time.timestamp() * 1000)

        # Call Binance 1m klines API
        import requests
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {
            "symbol": trade.pair.upper(),
            "interval": "1m",
            "startTime": start_ts,
            "endTime": end_ts,
            "limit": 1500
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            klines = res.json()
            if klines:
                highs = [float(k[2]) for k in klines]
                lows = [float(k[3]) for k in klines]
                max_high = max(highs)
                min_low = min(lows)

                if trade.direction == "LONG":
                    trade.mfe_price = Decimal(str(max_high))
                    trade.mae_price = Decimal(str(min_low))
                else:
                    trade.mfe_price = Decimal(str(min_low))
                    trade.mae_price = Decimal(str(max_high))

                db.commit()
                logger.info(f"✅ MFE/MAE captured for trade {trade_id}: MFE={trade.mfe_price}, MAE={trade.mae_price}")
                return {"status": "success", "mfe": float(trade.mfe_price), "mae": float(trade.mae_price)}

        return {"status": "failed", "reason": "Binance API call returned no klines"}

    except Exception as e:
        logger.error(f"Error in capture_mfe_mae task for trade {trade_id}: {e}")
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
