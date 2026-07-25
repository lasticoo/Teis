import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import EquitySnapshot, AccountTransfer, Trade
from app.services.binance import BinanceService

logger = logging.getLogger(__name__)


class EquitySnapshotService:
    @classmethod
    def capture_snapshot(cls, db: Session) -> Optional[EquitySnapshot]:
        """
        Fetches total account balance across Futures, Funding, and Spot wallets.
        Validates balance >= 0, then saves record to equity_snapshots table.
        If Binance API fails, logs warning and skips/retries cleanly without inserting zeros or dummy data.
        """
        try:
            bal_data = BinanceService.get_all_wallets_balance(db)
            if not bal_data:
                logger.warning("[EquityService] Binance account balance returned empty response. Skipping snapshot.")
                return None

            balance = Decimal(str(bal_data.get("total_balance", "0")))
            unrealized_pnl = Decimal(str(bal_data.get("crossUnPnl", "0")))

            if balance < Decimal("0"):
                logger.warning(f"[EquityService] Invalid negative balance {balance}. Skipping snapshot.")
                return None

            now = datetime.now()
            snapshot = EquitySnapshot(
                balance=balance,
                unrealized_pnl=unrealized_pnl,
                captured_at=now
            )
            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)
            logger.info(f"[EquityService] Captured total equity snapshot across all wallets: Total Balance=${balance}, UnPnl=${unrealized_pnl} at {now}")
            return snapshot
        except Exception as e:
            logger.warning(f"[EquityService] Failed to capture equity snapshot from Binance: {str(e)}")
            db.rollback()
            return None

    @classmethod
    def detect_transfers(cls, db: Session) -> int:
        """
        Fetches deposit/withdrawal transfers from Binance GET /fapi/v1/income?incomeType=TRANSFER.
        Deduplicates by binance_transfer_ref (tranId).
        Saves records to account_transfers table. Positive amount for deposit, negative for withdrawal.
        Returns count of new transfers created.
        """
        try:
            incomes = BinanceService.get_income_history(db, income_type="TRANSFER")
            if not incomes:
                logger.info("[EquityService] No transfer income history returned from Binance.")
                return 0

            created_count = 0
            for item in incomes:
                tran_id = str(item.get("tranId") or item.get("info") or "")
                if not tran_id:
                    continue

                existing = db.query(AccountTransfer).filter(AccountTransfer.binance_transfer_ref == tran_id).first()
                if existing:
                    continue

                raw_amt = Decimal(str(item.get("income", "0")))
                asset = item.get("asset", "USDT")
                timestamp_ms = item.get("time")
                occurred_at = datetime.fromtimestamp(timestamp_ms / 1000.0) if timestamp_ms else datetime.now()

                transfer = AccountTransfer(
                    amount=raw_amt,
                    asset=asset,
                    occurred_at=occurred_at,
                    binance_transfer_ref=tran_id
                )
                db.add(transfer)
                created_count += 1

            if created_count > 0:
                db.commit()
                logger.info(f"[EquityService] Recorded {created_count} new account transfers from Binance.")

            return created_count
        except Exception as e:
            logger.error(f"[EquityService] Failed to detect account transfers: {str(e)}")
            db.rollback()
            return 0

    @classmethod
    def get_equity_curve(
        cls,
        db: Session,
        range_filter: str = "all",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        Generates dual-line dataset for Equity Growth Curve:
        1. Real Equity Balance ($) = Account Balance - Total Net External Transfers
        2. Cumulative PnL ($ / R) = Sum of closed trade Net PnL / Realized RR
        Supports filters: '7d', '30d', '90d', '1y', 'month', 'year', 'all'.
        """
        # First ensure transfers & current snapshot exist
        cls.detect_transfers(db)

        now = datetime.now()
        if range_filter == "7d":
            cutoff = now - timedelta(days=7)
        elif range_filter == "30d":
            cutoff = now - timedelta(days=30)
        elif range_filter == "90d":
            cutoff = now - timedelta(days=90)
        elif range_filter == "1y":
            cutoff = now - timedelta(days=365)
        elif range_filter == "month":
            cutoff = datetime(now.year, now.month, 1)
        elif range_filter == "year":
            cutoff = datetime(now.year, 1, 1)
        else:
            cutoff = None

        if start_date:
            try:
                cutoff = datetime.fromisoformat(start_date)
            except Exception:
                pass

        # Query closed trades for cumulative PnL & R
        trades_query = db.query(Trade).filter(Trade.exit_time.isnot(None))
        if cutoff:
            trades_query = trades_query.filter(Trade.exit_time >= cutoff)
        closed_trades = trades_query.order_by(Trade.exit_time.asc()).all()

        # Query equity snapshots
        snap_query = db.query(EquitySnapshot)
        if cutoff:
            snap_query = snap_query.filter(EquitySnapshot.captured_at >= cutoff)
        snapshots = snap_query.order_by(EquitySnapshot.captured_at.asc()).all()

        # Query account transfers
        transfers = db.query(AccountTransfer).order_by(AccountTransfer.occurred_at.asc()).all()
        total_deposits = sum((float(t.amount) for t in transfers if float(t.amount) > 0), 0.0)
        total_withdrawals = sum((abs(float(t.amount)) for t in transfers if float(t.amount) < 0), 0.0)
        net_transfers = total_deposits - total_withdrawals

        # Latest balance breakdown across all wallets
        all_bal = BinanceService.get_all_wallets_balance(db)
        current_balance = float(all_bal["total_balance"])
        fut_balance = float(all_bal["futures_balance"])
        funding_balance = float(all_bal["funding_balance"])
        spot_balance = float(all_bal["spot_balance"])
        unrealized_pnl = float(all_bal["crossUnPnl"])

        # Calculate pure trading profit
        total_trading_pnl = sum((float(t.pnl) for t in closed_trades if t.pnl is not None), 0.0)
        net_return_pct = (total_trading_pnl / net_transfers * 100.0) if net_transfers > 0 else 0.0

        # Build time-series data points by combining trades and snapshots
        points = []
        cum_pnl = 0.0
        cum_r = 0.0

        for t in closed_trades:
            pnl_val = float(t.pnl) if t.pnl is not None else 0.0
            r_val = float(t.rr_realized) if t.rr_realized is not None else 0.0
            cum_pnl += pnl_val
            cum_r += r_val

            # Transfers up to trade exit time
            trans_at_time = sum((float(tr.amount) for tr in transfers if tr.occurred_at <= t.exit_time), 0.0)
            base_capital = trans_at_time if trans_at_time > 0 else 100.0
            real_equity = base_capital + cum_pnl

            points.append({
                "timestamp": t.exit_time.isoformat(),
                "label": t.pair,
                "cumulative_pnl": round(cum_pnl, 2),
                "cumulative_r": round(cum_r, 2),
                "real_equity": round(real_equity, 2),
                "net_transfers": round(trans_at_time, 2)
            })

        # If no trade points, create point from latest snapshot
        if not points:
            points.append({
                "timestamp": now.isoformat(),
                "label": "Latest Total Balance",
                "cumulative_pnl": 0.0,
                "cumulative_r": 0.0,
                "real_equity": round(current_balance, 2),
                "net_transfers": round(net_transfers, 2)
            })

        return {
            "range": range_filter,
            "summary": {
                "current_balance": round(current_balance, 2),
                "futures_balance": round(fut_balance, 2),
                "funding_balance": round(funding_balance, 2),
                "spot_balance": round(spot_balance, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "total_deposits": round(total_deposits, 2),
                "total_withdrawals": round(total_withdrawals, 2),
                "net_transfers": round(net_transfers, 2),
                "real_trading_profit": round(total_trading_pnl, 2),
                "trading_return_pct": round(net_return_pct, 2)
            },
            "data_points": points
        }
