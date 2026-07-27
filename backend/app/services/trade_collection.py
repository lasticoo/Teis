import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.models import Trade, ExchangeFill, TradeFill, TradeExecution

logger = logging.getLogger(__name__)

# Default risk amount in USDT if trade.risk_amount is 0 or Null (to prevent division by zero)
DEFAULT_RISK_AMOUNT = Decimal("10.0")


class TradeCollectionService:
    """
    Service responsible for linking Binance execution fills (ExchangeFill) to journal trades (Trade),
    aggregating multi-fills using Volume-Weighted Average Price (VWAP),
    and computing net PnL, realized RR, commission fees, and holding time.
    """

    @staticmethod
    def calculate_vwap(fills: List[ExchangeFill]) -> Tuple[Decimal, Decimal]:
        """
        Calculates Volume-Weighted Average Price (VWAP) and Total Quantity from a list of ExchangeFills.
        Formula: VWAP = Sum(price * qty) / Sum(qty)
        Returns: (vwap_price, total_qty)
        """
        if not fills:
            return Decimal("0.0"), Decimal("0.0")

        total_qty = Decimal("0.0")
        total_cost = Decimal("0.0")

        for fill in fills:
            qty = Decimal(str(fill.qty))
            price = Decimal(str(fill.price))
            total_qty += qty
            total_cost += price * qty

        if total_qty == Decimal("0.0"):
            return Decimal("0.0"), Decimal("0.0")

        vwap_price = total_cost / total_qty
        return vwap_price, total_qty

    @staticmethod
    def calculate_financials(
        trade: Trade,
        entry_fills: List[ExchangeFill],
        exit_fills: List[ExchangeFill],
        default_risk_amount: Decimal = DEFAULT_RISK_AMOUNT,
    ) -> Dict[str, Any]:
        """
        Calculates financial performance metrics:
        - VWAP entry & exit prices
        - Gross PnL, Total Commission Fee, Total Funding Fee, Net PnL
        - Realized Risk-to-Reward (RR)
        - Holding Time in seconds
        """
        vwap_entry, total_entry_qty = TradeCollectionService.calculate_vwap(entry_fills)
        vwap_exit, total_exit_qty = TradeCollectionService.calculate_vwap(exit_fills)

        # Total Commission Fee across all entry and exit fills
        all_fills = entry_fills + exit_fills
        total_commission_fee = sum((Decimal(str(f.fee)) for f in all_fills), Decimal("0.0"))

        # Total Funding Fee across all entry and exit fills
        total_funding_fee = sum(
            (Decimal(str(f.funding_fee or "0.0")) for f in all_fills), Decimal("0.0")
        )

        # Calculate Gross PnL from raw_payload in exit fills
        gross_pnl = Decimal("0.0")
        for f in exit_fills:
            if f.raw_payload and isinstance(f.raw_payload, dict):
                realized = f.raw_payload.get("realizedPnl", "0.0")
                gross_pnl += Decimal(str(realized))
            elif f.price and f.qty:
                # Theoretical fallback if raw_payload is missing
                entry_p = Decimal(str(trade.entry_price))
                exit_p = Decimal(str(f.price))
                qty = Decimal(str(f.qty))
                if trade.direction == "long":
                    gross_pnl += (exit_p - entry_p) * qty
                else:
                    gross_pnl += (entry_p - exit_p) * qty

        # Net PnL = Gross PnL - Total Commission Fee - Total Funding Fee
        net_pnl = gross_pnl - total_commission_fee - total_funding_fee

        # Use Dynamic 1R Binance Equity Model (1.0% of Total Binance Equity)
        try:
            from app.api.journal import get_dynamic_1r_risk_amount
            risk_amt = Decimal(str(round(get_dynamic_1r_risk_amount(db, 1.0), 6)))
        except Exception:
            risk_amt = Decimal("1.0")

        # Realized RR = Net PnL / Dynamic 1R Equity Risk
        rr_realized = net_pnl / risk_amt if risk_amt > Decimal("0.0") else Decimal("0.0")

        # Holding Time
        entry_dt = trade.entry_time
        exit_dt = (
            max((f.executed_at for f in exit_fills), default=datetime.now())
            if exit_fills
            else None
        )

        holding_time_sec = None
        if entry_dt and exit_dt:
            t_entry = entry_dt.replace(tzinfo=None)
            t_exit = exit_dt.replace(tzinfo=None)
            holding_time_sec = int((t_exit - t_entry).total_seconds())

        return {
            "vwap_entry": vwap_entry if total_entry_qty > Decimal("0.0") else Decimal(str(trade.entry_price)),
            "vwap_exit": vwap_exit if total_exit_qty > Decimal("0.0") else (trade.exit_price or trade.entry_price),
            "total_entry_qty": total_entry_qty,
            "total_exit_qty": total_exit_qty,
            "gross_pnl": gross_pnl,
            "commission_fee": total_commission_fee,
            "funding_fee": total_funding_fee,
            "total_fee": total_commission_fee + total_funding_fee,
            "net_pnl": net_pnl,
            "risk_amount": risk_amt,
            "rr_realized": round(rr_realized, 2),
            "exit_time": exit_dt,
            "holding_time_sec": holding_time_sec,
        }

    @staticmethod
    def auto_match_unlinked_fills(db: Session, trade: Trade):
        """
        Scans exchange_fills for matching symbol and time range, linking unlinked entry/exit fills to trade_fills.
        """
        from datetime import timedelta
        entry_side = "BUY" if trade.direction == "long" else "SELL"
        exit_side = "SELL" if trade.direction == "long" else "BUY"

        candidate_fills = (
            db.query(ExchangeFill)
            .filter(ExchangeFill.symbol == trade.pair)
            .order_by(ExchangeFill.executed_at.asc())
            .all()
        )

        for ef in candidate_fills:
            already_linked = (
                db.query(TradeFill)
                .filter(TradeFill.trade_id == trade.id, TradeFill.exchange_fill_id == ef.id)
                .first()
            )
            if already_linked:
                continue

            ef_time = ef.executed_at.replace(tzinfo=None) if ef.executed_at else None
            tr_entry_time = trade.entry_time.replace(tzinfo=None) if trade.entry_time else None

            if not ef_time or not tr_entry_time:
                continue

            # Entry fill: same side, executed close to entry_time (within 5 minutes)
            if ef.side == entry_side and abs((ef_time - tr_entry_time).total_seconds()) <= 300:
                tf = TradeFill(trade_id=trade.id, exchange_fill_id=ef.id, role="entry")
                db.add(tf)
            # Exit fill: opposite side, executed after entry_time
            elif ef.side == exit_side and ef_time >= (tr_entry_time - timedelta(seconds=60)):
                tf = TradeFill(trade_id=trade.id, exchange_fill_id=ef.id, role="exit")
                db.add(tf)

        db.flush()

    @staticmethod
    def link_trade_fills(db: Session, trade_id: str) -> Dict[str, Any]:
        """
        Links exchange fills to trade, aggregates multi-fills, updates financial metrics in MySQL DB.
        """
        trade = db.query(Trade).filter(Trade.id == trade_id).first()
        if not trade:
            logger.error(f"Trade {trade_id} not found for linking.")
            return {"status": "failed", "reason": "trade_not_found"}

        # First auto-match any unlinked fills for this trade's symbol
        TradeCollectionService.auto_match_unlinked_fills(db, trade)

        # Query all linked fills from trade_fills
        entry_tf_list = (
            db.query(TradeFill)
            .filter(TradeFill.trade_id == trade_id, TradeFill.role == "entry")
            .all()
        )

        exit_tf_list = (
            db.query(TradeFill)
            .filter(TradeFill.trade_id == trade_id, TradeFill.role == "exit")
            .all()
        )

        entry_fills = [tf.exchange_fill for tf in entry_tf_list if tf.exchange_fill]
        exit_fills = [tf.exchange_fill for tf in exit_tf_list if tf.exchange_fill]

        if not entry_fills:
            logger.warning(
                f"No entry fills linked for trade {trade_id} ({trade.pair}). Status: pending sync."
            )
            return {"status": "pending_sync", "reason": "missing_entry_fills"}

        # Calculate metrics
        financials = TradeCollectionService.calculate_financials(trade, entry_fills, exit_fills)

        # Update Trade record
        trade.entry_price = financials["vwap_entry"]
        if exit_fills:
            trade.exit_price = financials["vwap_exit"]
            trade.exit_time = financials["exit_time"]

        trade.pnl = financials["net_pnl"]
        trade.fee = financials["total_fee"]
        trade.rr_realized = financials["rr_realized"]
        trade.risk_amount = financials["risk_amount"]

        # Auto-detect TradeExecution parameters if exit_reason is missing
        exec_rec = db.query(TradeExecution).filter(TradeExecution.trade_id == trade_id).first()
        if not exec_rec:
            exec_rec = TradeExecution(trade_id=trade_id, order_type="market")
            db.add(exec_rec)

        if exit_fills:
            sl = float(trade.stop_loss) if trade.stop_loss else None
            tp = float(trade.take_profit) if trade.take_profit else None
            entry_p = float(trade.entry_price) if trade.entry_price else 0.0
            exit_p = float(trade.exit_price) if trade.exit_price else entry_p
            rr = float(trade.rr_realized) if trade.rr_realized is not None else 0.0

            # 1. Check if Stop Loss was hit (within 3% tolerance of SL distance)
            is_sl_hit = False
            if sl is not None and entry_p > 0:
                sl_dist = abs(entry_p - sl)
                if sl_dist > 0 and abs(exit_p - sl) <= (sl_dist * 0.03):
                    is_sl_hit = True

            # 2. Check if Take Profit was hit (within 3% tolerance of TP distance)
            is_tp_hit = False
            if tp is not None and entry_p > 0:
                tp_dist = abs(tp - entry_p)
                if tp_dist > 0 and abs(exit_p - tp) <= (tp_dist * 0.03):
                    is_tp_hit = True

            # 3. Check if Breakeven (BE) radius (|RR| <= 0.05R or exit price within 0.08% of entry)
            is_be_radius = (abs(rr) <= 0.05) or (entry_p > 0 and (abs(exit_p - entry_p) / entry_p) <= 0.0008)

            if is_sl_hit:
                exec_rec.exit_reason = "stop_loss"
            elif is_tp_hit:
                exec_rec.exit_reason = "take_profit"
            elif is_be_radius and exec_rec.moved_to_breakeven:
                exec_rec.exit_reason = "breakeven"
            else:
                exec_rec.exit_reason = "manual_close"

        if trade.stop_loss and trade.entry_price:
            sl = float(trade.stop_loss)
            entry_p = float(trade.entry_price)
            if (trade.direction == "long" and sl > entry_p) or (trade.direction == "short" and sl < entry_p):
                exec_rec.moved_to_breakeven = True

        db.commit()
        logger.info(
            f"Successfully linked trade {trade_id} ({trade.pair}). "
            f"Net PnL: {trade.pnl}, Realized RR: {trade.rr_realized}, Total Fee: {trade.fee}"
        )

        return {
            "status": "success" if exit_fills else "pending_sync",
            "trade_id": trade_id,
            "net_pnl": str(trade.pnl),
            "rr_realized": str(trade.rr_realized),
            "total_fee": str(trade.fee),
        }

