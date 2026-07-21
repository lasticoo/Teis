import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.models import Trade, ExchangeFill, TradeFill

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

        # Risk amount for RR calculation (fallback to default_risk_amount if 0 or None)
        risk_amt = (
            Decimal(str(trade.risk_amount))
            if (trade.risk_amount and Decimal(str(trade.risk_amount)) > Decimal("0.0"))
            else default_risk_amount
        )

        # Realized RR = Net PnL / Risk Amount
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
    def link_trade_fills(db: Session, trade_id: str) -> Dict[str, Any]:
        """
        Links exchange fills to trade, aggregates multi-fills, updates financial metrics in MySQL DB.
        """
        trade = db.query(Trade).filter(Trade.id == trade_id).first()
        if not trade:
            logger.error(f"Trade {trade_id} not found for linking.")
            return {"status": "failed", "reason": "trade_not_found"}

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
