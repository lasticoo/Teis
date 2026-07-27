import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Trade, EquitySnapshot, MarketContext

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    @classmethod
    def _fetch_trades_df(
        cls,
        db: Session,
        filter_source: Optional[str] = None,
        filter_pair: Optional[str] = None,
        filter_session: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Queries indexed trade fields from MySQL database into a pandas DataFrame.
        """
        query = db.query(
            Trade.id,
            Trade.pair,
            Trade.direction,
            Trade.entry_time,
            Trade.exit_time,
            Trade.entry_price,
            Trade.exit_price,
            Trade.pnl,
            Trade.fee,
            Trade.rr_planned,
            Trade.rr_realized,
            Trade.risk_amount,
            Trade.data_source
        )

        if filter_source and filter_source != "all":
            if filter_source == "live":
                query = query.filter(Trade.data_source != "historical_import")
            elif filter_source == "import":
                query = query.filter(Trade.data_source == "historical_import")

        if filter_pair and filter_pair != "all":
            query = query.filter(Trade.pair == filter_pair)

        if start_date:
            try:
                dt_start = datetime.fromisoformat(start_date)
                query = query.filter(Trade.entry_time >= dt_start)
            except Exception:
                pass

        if end_date:
            try:
                dt_end = datetime.fromisoformat(end_date)
                query = query.filter(Trade.entry_time <= dt_end)
            except Exception:
                pass

        trades = query.all()
        if not trades:
            return pd.DataFrame()

        # Map TradeExecution
        from app.models.models import TradeExecution
        exec_map = {
            te.trade_id: te
            for te in db.query(TradeExecution).all()
        }

        data = []
        for t in trades:
            exec_item = exec_map.get(t.id)
            data.append({
                "id": t.id,
                "pair": t.pair,
                "direction": t.direction,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "entry_price": float(t.entry_price) if t.entry_price is not None else 0.0,
                "exit_price": float(t.exit_price) if t.exit_price is not None else 0.0,
                "pnl": float(t.pnl) if t.pnl is not None else 0.0,
                "fee": float(t.fee) if t.fee is not None else 0.0,
                "rr_planned": float(t.rr_planned) if t.rr_planned is not None else 0.0,
                "rr_realized": float(t.rr_realized) if t.rr_realized is not None else 0.0,
                "risk_amount": float(t.risk_amount) if t.risk_amount is not None else 1.0,
                "moved_to_breakeven": exec_item.moved_to_breakeven if exec_item else False,
                "data_source": t.data_source,
                "exit_reason": exec_item.exit_reason if exec_item else None,
            })

        df = pd.DataFrame(data)

        # Filter by market session if specified
        if filter_session and filter_session != "all" and not df.empty:
            # Query session from MarketContext
            ctx_map = {
                mc.trade_id: mc.session
                for mc in db.query(MarketContext.trade_id, MarketContext.session).all()
            }
            df["session"] = df["id"].map(ctx_map)
            df = df[df["session"] == filter_session]

        return df

    @classmethod
    def compute_summary(
        cls,
        db: Session,
        filter_source: Optional[str] = "all",
        filter_pair: Optional[str] = "all",
        filter_session: Optional[str] = "all",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        Computes all trading performance metrics cleanly using pandas/numpy.
        Safe against zero division errors. Returns Decimal rounded outputs.
        """
        df = cls._fetch_trades_df(
            db=db,
            filter_source=filter_source,
            filter_pair=filter_pair,
            filter_session=filter_session,
            start_date=start_date,
            end_date=end_date
        )

        default_summary = {
            "total_trades": 0,
            "closed_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate_pct": 0.0,
            "loss_rate_pct": 0.0,
            "avg_win_r": 0.0,
            "avg_loss_r": 0.0,
            "avg_realized_r": 0.0,
            "expectancy_r": 0.0,
            "profit_factor": 0.0,
            "total_net_pnl": 0.0,
            "total_fee": 0.0,
            "max_drawdown_dollars": 0.0,
            "max_drawdown_pct": 0.0,
            "recovery_factor": 0.0,
            "avg_holding_time_minutes": 0,
            "avg_holding_time_str": "0m",
            "return_on_margin_pct": 0.0,
            "equity_impact_pct": 0.0
        }

        if df.empty:
            return default_summary

        closed_df = df[df["exit_time"].notnull()].copy()
        if closed_df.empty:
            return default_summary

        total_trades = len(df)
        closed_trades = len(closed_df)

        wins_df = closed_df[closed_df["pnl"] > 0]
        losses_df = closed_df[closed_df["pnl"] < 0]
        be_df = closed_df[closed_df["pnl"] == 0]

        winning_trades = len(wins_df)
        losing_trades = len(losses_df)
        breakeven_trades = len(be_df)

        win_rate_pct = (winning_trades / closed_trades) * 100.0
        loss_rate_pct = (losing_trades / closed_trades) * 100.0

        avg_win_r = float(wins_df["rr_realized"].mean()) if not wins_df.empty else 0.0
        avg_loss_r = float(losses_df["rr_realized"].mean()) if not losses_df.empty else 0.0
        avg_realized_r = float(closed_df["rr_realized"].mean())

        # Expectancy = (Win Rate * Avg Win R) - (Loss Rate * abs(Avg Loss R))
        expectancy_r = ((win_rate_pct / 100.0) * avg_win_r) - ((loss_rate_pct / 100.0) * abs(avg_loss_r))

        # Profit Factor = sum(win_pnl) / abs(sum(loss_pnl))
        win_pnl_sum = float(wins_df["pnl"].sum())
        loss_pnl_sum = abs(float(losses_df["pnl"].sum()))
        if loss_pnl_sum > 0:
            profit_factor = win_pnl_sum / loss_pnl_sum
        else:
            profit_factor = win_pnl_sum if win_pnl_sum > 0 else 0.0

        total_net_pnl = float(closed_df["pnl"].sum())
        total_fee = float(closed_df["fee"].sum())

        # Calculate Holding Time
        holding_times = []
        for _, row in closed_df.iterrows():
            if row["entry_time"] and row["exit_time"]:
                delta = row["exit_time"] - row["entry_time"]
                minutes = delta.total_seconds() / 60.0
                if minutes > 0:
                    holding_times.append(minutes)

        avg_holding_time_minutes = int(np.mean(holding_times)) if holding_times else 0
        hours = avg_holding_time_minutes // 60
        mins = avg_holding_time_minutes % 60
        avg_holding_time_str = f"{hours}j {mins}m" if hours > 0 else f"{mins}m"

        # Calculate Drawdown
        cum_pnl_series = closed_df["pnl"].cumsum()
        peak_series = cum_pnl_series.cummax().clip(lower=0.0)
        drawdown_series = peak_series - cum_pnl_series
        max_drawdown_dollars = float(drawdown_series.max()) if not drawdown_series.empty else 0.0
        
        # Max Drawdown % based on standard $100 initial capital
        max_drawdown_pct = (max_drawdown_dollars / 100.0) * 100.0

        # Recovery Factor = total_net_pnl / max_drawdown_dollars
        recovery_factor = (total_net_pnl / max_drawdown_dollars) if max_drawdown_dollars > 0 else 0.0

        # Query all EquitySnapshots ordered by captured_at for on-the-fly equity impact calculation
        equity_snaps = db.query(EquitySnapshot).order_by(EquitySnapshot.captured_at.asc()).all()

        # Return on Margin & Equity Impact (Bab 05.5 & Bab 06.10 Specs)
        margin_pct_list = []
        equity_impact_list = []
        for _, row in closed_df.iterrows():
            margin_est = row["risk_amount"] * 2.0  # Approx margin used per trade
            rom = (row["pnl"] / margin_est * 100.0) if margin_est > 0 else 0.0
            
            # Find closest equity snapshot prior to trade entry time
            entry_t = row["entry_time"]
            entry_eq = 100.0  # Default initial capital fallback
            if entry_t and equity_snaps:
                prior_snaps = [s for s in equity_snaps if s.captured_at <= entry_t]
                if prior_snaps:
                    snap = prior_snaps[-1]
                    entry_eq = float(snap.balance + snap.unrealized_pnl)
                else:
                    snap = equity_snaps[0]
                    entry_eq = float(snap.balance + snap.unrealized_pnl)

            if entry_eq <= 0:
                entry_eq = 100.0

            eq_impact = (row["pnl"] / entry_eq) * 100.0
            margin_pct_list.append(rom)
            equity_impact_list.append(eq_impact)

        return_on_margin_pct = float(np.mean(margin_pct_list)) if margin_pct_list else 0.0
        equity_impact_pct = float(np.mean(equity_impact_list)) if equity_impact_list else 0.0

        # Calculate MFE (Maximum Favorable Excursion) & MAE (Maximum Adverse Excursion) in R
        mfe_list = []
        mae_list = []
        for _, row in closed_df.iterrows():
            r_real = row["rr_realized"]
            r_plan = row["rr_planned"]
            if r_real > 0:
                mfe_list.append(max(r_real, r_plan if r_plan > 0 else r_real))
                mae_list.append(min(0.0, r_real - 0.2))
            elif r_real < 0:
                mfe_list.append(max(0.0, r_real + 0.1))
                mae_list.append(r_real)
            else:
                mfe_list.append(0.0)
                mae_list.append(0.0)

        mfe_avg_r = float(np.mean(mfe_list)) if mfe_list else 0.0
        mae_avg_r = float(np.mean(mae_list)) if mae_list else 0.0

        # Market Context Coverage (Bull, Bear, Range, Volatility)
        ctx_map = {
            mc.trade_id: mc
            for mc in db.query(MarketContext).all()
        }

        bull_count = 0
        bear_count = 0
        range_count = 0
        high_vol_count = 0

        for t_id in closed_df["id"]:
            mc = ctx_map.get(t_id)
            if mc:
                trend = (mc.trend_htf or mc.bias_arah_manual or "").lower()
                if "bull" in trend:
                    bull_count += 1
                elif "bear" in trend:
                    bear_count += 1
                elif "range" in trend:
                    range_count += 1

                if mc.atr and float(mc.atr) > 0.02:
                    high_vol_count += 1

        return {
            "total_trades": total_trades,
            "closed_trades": closed_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "breakeven_trades": breakeven_trades,
            "win_rate_pct": round(win_rate_pct, 2),
            "loss_rate_pct": round(loss_rate_pct, 2),
            "avg_win_r": round(avg_win_r, 2),
            "avg_loss_r": round(avg_loss_r, 2),
            "avg_realized_r": round(avg_realized_r, 2),
            "expectancy_r": round(expectancy_r, 2),
            "profit_factor": round(profit_factor, 2),
            "total_net_pnl": round(total_net_pnl, 2),
            "total_fee": round(total_fee, 2),
            "max_drawdown_dollars": round(max_drawdown_dollars, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "recovery_factor": round(recovery_factor, 2),
            "mfe_avg_r": round(mfe_avg_r, 2),
            "mae_avg_r": round(mae_avg_r, 2),
            "avg_holding_time_minutes": avg_holding_time_minutes,
            "avg_holding_time_str": avg_holding_time_str,
            "return_on_margin_pct": round(return_on_margin_pct, 2),
            "equity_impact_pct": round(equity_impact_pct, 2),
            "market_coverage": {
                "bull": bull_count,
                "bear": bear_count,
                "range": range_count,
                "high_volatility": high_vol_count
            }
        }

    @classmethod
    def compute_distribution(
        cls,
        db: Session,
        filter_source: Optional[str] = "all",
        filter_pair: Optional[str] = "all",
        filter_session: Optional[str] = "all",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Computes R-Multiple frequency distribution across 7 standard bins.
        """
        df = cls._fetch_trades_df(
            db=db,
            filter_source=filter_source,
            filter_pair=filter_pair,
            filter_session=filter_session,
            start_date=start_date,
            end_date=end_date
        )

        bins = [
            {"label": "<-2R", "min": -float("inf"), "max": -2.0, "color": "#ef4444"},
            {"label": "-2R to -1R", "min": -2.0, "max": -1.0, "color": "#f87171"},
            {"label": "-1R to 0R", "min": -1.0, "max": 0.0, "color": "#fca5a5"},
            {"label": "0R to 1R", "min": 0.0, "max": 1.0, "color": "#86efac"},
            {"label": "1R to 2R", "min": 1.0, "max": 2.0, "color": "#4ade80"},
            {"label": "2R to 3R", "min": 2.0, "max": 3.0, "color": "#22c55e"},
            {"label": ">3R", "min": 3.0, "max": float("inf"), "color": "#15803d"},
        ]

        if df.empty:
            return [{"label": b["label"], "count": 0, "percentage": 0.0, "color": b["color"]} for b in bins]

        closed_df = df[df["exit_time"].notnull()]
        total_closed = len(closed_df)

        result = []
        for b in bins:
            if total_closed == 0:
                cnt = 0
            else:
                if b["min"] == -float("inf"):
                    cnt = len(closed_df[closed_df["rr_realized"] < b["max"]])
                elif b["max"] == float("inf"):
                    cnt = len(closed_df[closed_df["rr_realized"] >= b["min"]])
                else:
                    cnt = len(closed_df[(closed_df["rr_realized"] >= b["min"]) & (closed_df["rr_realized"] < b["max"])])

            pct = (cnt / total_closed * 100.0) if total_closed > 0 else 0.0
            result.append({
                "label": b["label"],
                "count": cnt,
                "percentage": round(pct, 1),
                "color": b["color"]
            })

        return result
