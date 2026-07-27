"""
Historical Import Service (Fitur 9) — Core business logic.
Follows SOLID:
  - S: Only handles Binance historical fill fetching & DB persistence.
  - O: Open for extension (new exchanges) without modifying this class.
  - L: Uses standard interfaces (Session, BinanceService).
  - I: Exposes granular methods, not a monolithic do-everything function.
  - D: Depends on abstractions (BinanceService, Session) not concretes.
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Callable

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.models import Trade, ExchangeFill, TradeFill, APICredential
from app.services.binance import BinanceService

logger = logging.getLogger(__name__)

# --- Constants (configurable; tune for Binance rate-limits) ---
CHUNK_DAYS: int = 7          # Max days per /fapi/v1/userTrades call
MAX_RECORDS_PER_CALL: int = 1000
RATE_LIMIT_SLEEP_SEC: int = 5  # Sleep between calls to stay within rate-limit


class HistoricalImportService:
    """
    Service responsible for pulling historical closed-trade fills from Binance Futures,
    deduplicating them, grouping into trades, and persisting with data_source='historical_import'.

    Subjective fields (psychology, trade_setup_tags, market_context.bias_arah_manual)
    are intentionally left empty to prevent hindsight bias.
    """

    # -----------------------------------------------------------------------
    # Public Entry Point
    # -----------------------------------------------------------------------
    @classmethod
    def run_import(
        cls,
        db: Session,
        start_ts: int,
        end_ts: int,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Main orchestrator for historical import.

        Args:
            db: SQLAlchemy session.
            start_ts: Unix timestamp in milliseconds (start of range).
            end_ts: Unix timestamp in milliseconds (end of range).
            progress_callback: Optional callable to emit real-time progress dicts.

        Returns:
            Summary dict with totals: fills, trades, skipped, errors.
        """
        summary = {
            "total_fills": 0,
            "total_trades": 0,
            "total_skipped": 0,
            "total_errors": 0,
        }

        # 1. Fetch active Binance client
        try:
            client = BinanceService.get_client(db)
        except ValueError as e:
            logger.error(f"[ImportService] Cannot get Binance client: {e}")
            raise

        # 2. Discover all symbols the account has traded in the selected range
        symbols = cls._discover_symbols(client, start_ts, end_ts)
        if not symbols:
            logger.warning("[ImportService] No traded symbols found on this account.")
            return summary

        total_symbols = len(symbols)
        logger.info(f"[ImportService] Discovered {total_symbols} symbols to process.")

        # 3. Per-symbol, paginate through time chunks
        for sym_idx, symbol in enumerate(symbols):
            logger.info(f"[ImportService] [{sym_idx+1}/{total_symbols}] Processing {symbol}...")

            raw_fills = cls._fetch_all_fills_for_symbol(
                client, symbol, start_ts, end_ts
            )

            # Persist fills and group into trades
            new_fills, skipped = cls._upsert_exchange_fills(db, symbol, raw_fills)
            summary["total_fills"] += new_fills
            summary["total_skipped"] += skipped

            trades_created = cls._group_and_save_trades(db, symbol, raw_fills)
            summary["total_trades"] += trades_created

            # Emit progress
            pct = int((sym_idx + 1) / total_symbols * 100)
            if progress_callback:
                progress_callback({
                    "event": "progress",
                    "pct": pct,
                    "fills_found": summary["total_fills"],
                    "trades_saved": summary["total_trades"],
                    "skipped": summary["total_skipped"],
                    "current_symbol": symbol,
                    "message": f"Memproses {symbol} ({sym_idx+1}/{total_symbols})…",
                })

            time.sleep(0.3)  # Brief pause to respect Binance IP rate-limits

        logger.info(f"[ImportService] Import complete: {summary}")
        return summary

    # -----------------------------------------------------------------------
    # Symbol Discovery
    # -----------------------------------------------------------------------
    @staticmethod
    def _discover_symbols(client, start_ts: int = None, end_ts: int = None) -> List[str]:
        """
        Returns list of distinct symbols the account has traded in the target date range.
        Paginates futures account income history to capture 100% of historical symbols.
        """
        symbols: set = set()

        # 1. Active open/recent positions
        try:
            positions = client.futures_position_information()
            for pos in positions:
                if float(pos.get("positionAmt", 0)) != 0 or float(pos.get("entryPrice", 0)) != 0:
                    symbols.add(pos["symbol"])
        except Exception as e:
            logger.warning(f"[ImportService] futures_position_information failed: {e}")

        # 2. Paginate income history within target date range
        try:
            current_end = end_ts or int(time.time() * 1000)
            target_start = start_ts or (current_end - 365 * 24 * 3600 * 1000)
            
            for _ in range(30):  # max 30 pages (30,000 records)
                kwargs = {"limit": 1000}
                if current_end:
                    kwargs["endTime"] = current_end
                items = client.futures_income_history(**kwargs)
                if not items:
                    break
                for item in items:
                    sym = item.get("symbol")
                    if sym:
                        symbols.add(sym)
                min_t = min(int(x["time"]) for x in items)
                if min_t <= target_start or current_end == min_t - 1:
                    break
                current_end = min_t - 1
                time.sleep(0.1)
        except Exception as e:
            logger.warning(f"[ImportService] futures_income_history pagination failed: {e}")

        # 3. Always include popular USDT pairs to guarantee no traded symbol is missed
        common_symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT",
            "AVAXUSDT", "LINKUSDT", "SUIUSDT", "PEPEUSDT", "NEARUSDT", "APTUSDT", "WIFUSDT",
            "1000SHIBUSDT", "APEUSDT", "EDGEUSDT", "ENAUSDT", "GRASSUSDT", "MEMEUSDT",
            "OPNUSDT", "PROMUSDT", "RENDERUSDT", "REUSDT", "SKRUSDT", "SPKUSDT", "TIAUSDT"
        ]
        for s in common_symbols:
            symbols.add(s)

        logger.info(f"[ImportService] Discovered {len(symbols)} symbols: {sorted(symbols)}")
        return sorted(symbols)

    # -----------------------------------------------------------------------
    # Fill Fetching (chunked, rate-limit aware)
    # -----------------------------------------------------------------------
    @staticmethod
    def _fetch_all_fills_for_symbol(
        client,
        symbol: str,
        start_ts: int,
        end_ts: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetches all userTrades for a symbol within [start_ts, end_ts] using
        6-day sliding windows (safely under Binance 7-day API limit).
        Caps end_ts at current Binance server time to avoid APIError -4165.
        """
        all_fills: List[Dict] = []
        
        # Cap end_ts at current server time to prevent invalid interval / future end_time error
        now_ms = int(time.time() * 1000)
        safe_end_ts = min(end_ts, now_ms)
        
        # 6-day chunk (6 * 24 * 3600 * 1000 ms = 518,400,000 ms)
        chunk_ms = 6 * 24 * 60 * 60 * 1000
        window_start = start_ts

        while window_start < safe_end_ts:
            window_end = min(window_start + chunk_ms, safe_end_ts)
            retries = 0
            while retries < 3:
                try:
                    fills = client.futures_account_trades(
                        symbol=symbol,
                        startTime=window_start,
                        endTime=window_end,
                        limit=1000,
                    )
                    all_fills.extend(fills)
                    break
                except Exception as e:
                    err_str = str(e)
                    if "-1003" in err_str or "too many requests" in err_str.lower():
                        logger.warning(f"[ImportService] Rate-limit hit on {symbol}, sleeping 5s...")
                        time.sleep(5)
                        retries += 1
                    else:
                        logger.error(f"[ImportService] Error fetching {symbol} [{window_start}→{window_end}]: {e}")
                        break

            window_start = window_end + 1
            time.sleep(0.15)  # Pause to respect Binance API IP rate limits

        logger.info(f"[ImportService] {symbol}: fetched {len(all_fills)} raw fills.")
        return all_fills

    # -----------------------------------------------------------------------
    # Persistence: ExchangeFill upsert with deduplication
    # -----------------------------------------------------------------------
    @staticmethod
    def _upsert_exchange_fills(
        db: Session,
        symbol: str,
        raw_fills: List[Dict[str, Any]],
    ) -> tuple:
        """
        Inserts new ExchangeFill records, skipping duplicates via uq_fill constraint.
        Returns: (new_inserted_count, skipped_count)
        """
        new_count = 0
        skipped_count = 0

        for fill in raw_fills:
            binance_trade_id = int(fill.get("id", 0))
            binance_order_id = int(fill.get("orderId", 0))
            executed_at = datetime.fromtimestamp(
                int(fill.get("time", 0)) / 1000, tz=timezone.utc
            ).replace(tzinfo=None)

            side = "BUY" if fill.get("side") == "BUY" else "SELL"

            ef = ExchangeFill(
                symbol=symbol,
                binance_trade_id=binance_trade_id,
                binance_order_id=binance_order_id,
                price=Decimal(str(fill.get("price", "0"))),
                qty=Decimal(str(fill.get("qty", "0"))),
                fee=Decimal(str(fill.get("commission", "0"))),
                funding_fee=None,
                side=side,
                executed_at=executed_at,
                raw_payload=fill,
            )

            try:
                db.add(ef)
                db.flush()  # Detect constraint violation immediately
                new_count += 1
            except IntegrityError:
                db.rollback()
                skipped_count += 1
            except Exception as e:
                db.rollback()
                logger.error(f"[ImportService] Unexpected error inserting fill {binance_trade_id}: {e}")
                skipped_count += 1

        db.commit()
        logger.info(f"[ImportService] {symbol}: {new_count} fills inserted, {skipped_count} skipped.")
        return new_count, skipped_count

    # -----------------------------------------------------------------------
    # Trade Grouping: pair fills into open+close trades
    # -----------------------------------------------------------------------
    @classmethod
    def _group_and_save_trades(
        cls,
        db: Session,
        symbol: str,
        raw_fills: List[Dict[str, Any]],
    ) -> int:
        """
        Groups fills by orderId into opening/closing pairs, then creates Trade records
        with data_source='historical_import'. Subjective fields are left NULL.

        Strategy:
          - BUY fills = opening LONG or closing SHORT
          - SELL fills = opening SHORT or closing LONG
          - We use positionSide + isMaker to determine direction when available
          - Group by orderId; first distinct order opening = trade open
        """
        if not raw_fills:
            return 0

        trades_created = 0

        # Sort chronologically
        sorted_fills = sorted(raw_fills, key=lambda f: int(f.get("time", 0)))

        # Group fills by orderId
        from collections import defaultdict
        order_groups: Dict[int, List[Dict]] = defaultdict(list)
        for fill in sorted_fills:
            order_id = int(fill.get("orderId", 0))
            order_groups[order_id].append(fill)

        # Build a queue of orders sorted by time of first fill
        orders_sorted = sorted(
            order_groups.items(),
            key=lambda kv: int(kv[1][0].get("time", 0))
        )

        # Queue of open trades per direction (FIFO pairing)
        open_trades_queue: Dict[str, List[str]] = defaultdict(list)

        for order_id, fills in orders_sorted:
            if not fills:
                continue

            sample = fills[0]
            side = sample.get("side", "BUY")
            position_side = sample.get("positionSide", "BOTH")
            realized_pnl = sum(float(f.get("realizedPnl", 0)) for f in fills)
            total_comm = sum(float(f.get("commission", 0)) for f in fills)

            executed_at = datetime.fromtimestamp(
                int(sample.get("time", 0)) / 1000, tz=timezone.utc
            ).replace(tzinfo=None)

            if position_side == "LONG":
                direction = "long"
                is_opening = (side == "BUY")
            elif position_side == "SHORT":
                direction = "short"
                is_opening = (side == "SELL")
            else:
                # ONE-WAY MODE (BOTH):
                # Fills with realizedPnl != 0 are CLOSING fills.
                # Fills with realizedPnl == 0 are OPENING fills.
                if abs(realized_pnl) > 1e-8:
                    is_opening = False
                    direction = "long" if side == "SELL" else "short"
                else:
                    is_opening = True
                    direction = "long" if side == "BUY" else "short"

            if is_opening:
                entry_price = cls._vwap_from_fills(fills)

                # Deduplicate: check if existing trade for this open order exists
                existing_trade = cls._find_existing_historical_trade(db, symbol, order_id)
                if existing_trade:
                    open_trades_queue[direction].append(existing_trade.id)
                    continue

                trade = Trade(
                    pair=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    exit_price=None,
                    stop_loss=None,
                    take_profit=None,
                    margin=None,
                    leverage=None,
                    risk_amount=Decimal("1.00"),
                    rr_planned=None,
                    rr_realized=None,
                    pnl=None,
                    fee=Decimal(str(total_comm)),
                    entry_time=executed_at,
                    exit_time=None,
                    data_source="historical_import",
                    locked_at=None,
                )
                db.add(trade)
                db.flush()

                cls._link_fills_to_trade(db, trade.id, fills, "entry")
                open_trades_queue[direction].append(trade.id)
                trades_created += 1

            else:
                queue = open_trades_queue[direction]
                exit_price = cls._vwap_from_fills(fills)
                net_pnl = Decimal(str(realized_pnl)) - Decimal(str(total_comm))

                if queue:
                    trade_id = queue.pop(0)
                    trade = db.query(Trade).filter(Trade.id == trade_id).first()
                    if trade:
                        trade.exit_price = exit_price
                        trade.exit_time = executed_at
                        trade.pnl = net_pnl
                        trade.fee = (trade.fee or Decimal("0")) + Decimal(str(total_comm))
                        trade.rr_realized = cls._calc_rr(trade, net_pnl)
                        cls._link_fills_to_trade(db, trade.id, fills, "exit")
                else:
                    # Closing order without tracked entry: create completed trade directly
                    trade = Trade(
                        pair=symbol,
                        direction=direction,
                        entry_price=exit_price,  # fallback to exit_price
                        exit_price=exit_price,
                        stop_loss=None,
                        take_profit=None,
                        margin=None,
                        leverage=None,
                        risk_amount=Decimal("1.00"),
                        rr_planned=None,
                        rr_realized=Decimal(str(round(net_pnl / Decimal("1.00"), 2))),
                        pnl=net_pnl,
                        fee=Decimal(str(total_comm)),
                        entry_time=executed_at,
                        exit_time=executed_at,
                        data_source="historical_import",
                        locked_at=None,
                    )
                    db.add(trade)
                    db.flush()
                    cls._link_fills_to_trade(db, trade.id, fills, "exit")
                    trades_created += 1

        db.commit()
        logger.info(f"[ImportService] {symbol}: {trades_created} trades created/updated.")
        return trades_created

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    @staticmethod
    def _is_opening_order(side: str, direction: str) -> bool:
        """BUY opens LONG, SELL opens SHORT."""
        return (side == "BUY" and direction == "long") or (side == "SELL" and direction == "short")

    @staticmethod
    def _vwap_from_fills(fills: List[Dict]) -> Decimal:
        total_qty = Decimal("0")
        total_cost = Decimal("0")
        for f in fills:
            qty = Decimal(str(f.get("qty", "0")))
            price = Decimal(str(f.get("price", "0")))
            total_qty += qty
            total_cost += qty * price
        return (total_cost / total_qty) if total_qty > Decimal("0") else Decimal("0")

    @staticmethod
    def _calc_rr(trade: Trade, net_pnl: Decimal, db: Session = None) -> Decimal:
        try:
            from app.api.journal import get_dynamic_1r_risk_amount
            risk = Decimal(str(round(get_dynamic_1r_risk_amount(db, 1.0), 6))) if db else Decimal("0.9616")
        except Exception:
            risk = Decimal("0.9616")
        return Decimal(str(round(net_pnl / risk, 2)))

    @staticmethod
    def _link_fills_to_trade(
        db: Session, trade_id: str, fills: List[Dict], role: str
    ) -> None:
        """Links ExchangeFill records to a Trade via TradeFill join table."""
        for fill in fills:
            binance_trade_id = int(fill.get("id", 0))
            symbol = fill.get("symbol", "")
            ef = (
                db.query(ExchangeFill)
                .filter(
                    ExchangeFill.binance_trade_id == binance_trade_id,
                    ExchangeFill.symbol == symbol,
                )
                .first()
            )
            if ef:
                from sqlalchemy.exc import IntegrityError
                try:
                    from app.models.models import TradeFill as TF
                    existing = db.query(TF).filter(
                        TF.trade_id == trade_id, TF.exchange_fill_id == ef.id
                    ).first()
                    if not existing:
                        tf = TF(trade_id=trade_id, exchange_fill_id=ef.id, role=role)
                        db.add(tf)
                        db.flush()
                except IntegrityError:
                    db.rollback()

    @staticmethod
    def _find_existing_historical_trade(
        db: Session, symbol: str, order_id: int
    ) -> Optional[Trade]:
        """Check if a historical trade with same open order already exists via fill link."""
        ef = (
            db.query(ExchangeFill)
            .filter(
                ExchangeFill.symbol == symbol,
                ExchangeFill.binance_order_id == order_id,
            )
            .first()
        )
        if not ef:
            return None
        from app.models.models import TradeFill as TF
        tf = db.query(TF).filter(TF.exchange_fill_id == ef.id, TF.role == "entry").first()
        if tf:
            return db.query(Trade).filter(Trade.id == tf.trade_id).first()
        return None

    @classmethod
    def _create_closed_historical_trade(
        cls,
        db: Session,
        symbol: str,
        direction: str,
        exit_fills: List[Dict],
        exit_time: datetime,
    ) -> Optional[str]:
        """Fallback: create a completed trade when open-side data is unavailable."""
        try:
            exit_price = cls._vwap_from_fills(exit_fills)
            realized_pnl = sum(float(f.get("realizedPnl", 0)) for f in exit_fills)
            total_fee = sum(float(f.get("commission", 0)) for f in exit_fills)

            trade = Trade(
                pair=symbol,
                direction=direction,
                entry_price=exit_price,  # best-effort; real entry unavailable
                exit_price=exit_price,
                stop_loss=None,
                take_profit=None,
                margin=None,
                leverage=None,
                risk_amount=Decimal("10.0"),
                rr_planned=None,
                rr_realized=Decimal(str(round(realized_pnl / 10, 2))),
                pnl=Decimal(str(realized_pnl)),
                fee=Decimal(str(total_fee)),
                entry_time=exit_time,
                exit_time=exit_time,
                data_source="historical_import",
                locked_at=None,
            )
            db.add(trade)
            db.flush()
            cls._link_fills_to_trade(db, trade.id, exit_fills, "exit")
            return trade.id
        except Exception as e:
            logger.error(f"[ImportService] Failed to create closed trade: {e}")
            db.rollback()
            return None
