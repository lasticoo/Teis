import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from app.models.models import Trade, TradeExecution, MarketContext, SetupTaxonomyVersion, TradeSetupTag


def create_synthetic_trade(
    pair: str = "BTCUSDT",
    direction: str = "LONG",
    entry_price: float = 50000.0,
    rr_realized: float = 1.0,
    entry_time: datetime = None,
    session: str = "london",
    tags: List[str] = None
) -> Dict[str, Any]:
    """Creates a dictionary payload representing a synthetic trade with deterministic parameters."""
    if entry_time is None:
        entry_time = datetime.now()
    if tags is None:
        tags = ["Order Block (H4)"]
        
    pnl = rr_realized * 10.0  # Assumes $10 per 1R
    
    return {
        "id": str(uuid.uuid4()),
        "pair": pair,
        "direction": direction,
        "entry_price": Decimal(str(entry_price)),
        "rr_realized": Decimal(str(rr_realized)),
        "r_realized": float(rr_realized),
        "pnl": Decimal(str(pnl)),
        "entry_time": entry_time,
        "exit_time": entry_time + timedelta(hours=2),
        "session": session,
        "tags": tags,
        "exit_reason": "take_profit" if rr_realized > 0 else "stop_loss"
    }


def generate_stable_winning_dataset(n: int = 40) -> List[Dict[str, Any]]:
    """
    Dataset A: 40 trades with consistent +0.50R expectancy (+1.5R win 60%, -1R loss 40%).
    Chronologically even across 3 periods.
    Expected: is_stable = True, Expectancy = +0.50R, CV <= 0.75.
    """
    trades = []
    base_time = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(n):
        t_time = base_time + timedelta(hours=i * 12)
        is_win = (i % 5 != 0 and i % 5 != 1)  # 60% win rate
        r_val = 1.5 if is_win else -1.0
        trades.append(create_synthetic_trade(
            pair="BTCUSDT" if i % 2 == 0 else "ETHUSDT",
            rr_realized=r_val,
            entry_time=t_time,
            session="london" if i % 3 == 0 else ("new_york" if i % 3 == 1 else "asia"),
            tags=["Order Block (H4)"]
        ))
    return trades


def generate_declining_trend_dataset(n: int = 40) -> List[Dict[str, Any]]:
    """
    Dataset B: 40 trades with strong early performance (+1.5R) and negative late performance (-0.8R).
    Expected: is_stable = False (period 3 mean <= 0 or CV > 0.75).
    """
    trades = []
    base_time = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(n):
        t_time = base_time + timedelta(hours=i * 12)
        if i < 20:
            r_val = 2.0 if i % 4 != 0 else -1.0  # +1.25R early
        else:
            r_val = -1.5 if i % 3 != 0 else 0.5   # -0.83R late
        trades.append(create_synthetic_trade(
            pair="BTCUSDT",
            rr_realized=r_val,
            entry_time=t_time,
            session="london",
            tags=["Order Block (H4)"]
        ))
    return trades


def generate_single_pair_session_dataset(n: int = 40) -> List[Dict[str, Any]]:
    """
    Dataset C: 40 trades with 1 positive pair (BTCUSDT) and 1 negative pair (ETHUSDT).
    Expected: is_repeatable = False (50% positive subgroup ratio < threshold or failing subgroup).
    """
    trades = []
    base_time = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(n):
        t_time = base_time + timedelta(hours=i * 12)
        # BTCUSDT is positive (+1.5R), ETHUSDT is negative (-1.5R)
        pair_val = "BTCUSDT" if i < 20 else "ETHUSDT"
        r_val = 1.5 if i < 20 else -1.5
        trades.append(create_synthetic_trade(
            pair=pair_val,
            rr_realized=r_val,
            entry_time=t_time,
            session="london",
            tags=["Order Block (H4)"]
        ))
    return trades


def generate_robust_wide_sl_tp_dataset(n: int = 40) -> List[Dict[str, Any]]:
    """
    Dataset D: 40 trades with wide profit targets (+3.0R win, -0.5R loss).
    Expected: is_robust = True across all 8 shift scenarios.
    """
    trades = []
    base_time = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(n):
        t_time = base_time + timedelta(hours=i * 12)
        r_val = 3.0 if i % 3 != 0 else -0.5  # High win rate & RR
        trades.append(create_synthetic_trade(
            pair="BTCUSDT" if i % 2 == 0 else "ETHUSDT",
            rr_realized=r_val,
            entry_time=t_time,
            session="london" if i % 2 == 0 else "new_york",
            tags=["Order Block (H4)"]
        ))
    return trades


def generate_lucky_outlier_dataset(n: int = 40) -> List[Dict[str, Any]]:
    """
    Dataset E: 40 trades where 38 trades are -0.1R losses, and only 2 trades are +1.0R.
    Expected: is_fdr_significant = False (high p-value / non-significant FDR).
    """
    trades = []
    base_time = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(n):
        t_time = base_time + timedelta(hours=i * 12)
        r_val = 1.0 if i in (0, 1) else -0.1
        trades.append(create_synthetic_trade(
            pair="BTCUSDT",
            rr_realized=r_val,
            entry_time=t_time,
            session="london",
            tags=["Order Block (H4)"]
        ))
    return trades
