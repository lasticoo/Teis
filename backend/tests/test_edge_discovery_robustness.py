import numpy as np
import pytest
from app.services.edge_discovery_engine import EdgeDiscoveryEngine
from tests.fixtures.synthetic_trades import generate_robust_wide_sl_tp_dataset, generate_lucky_outlier_dataset


def test_evaluate_robustness_with_wide_sl_tp_dataset():
    """
    Verifies that _evaluate_robustness returns (True, detail) for robust setups.
    Dataset D: 40 trades with wide profit targets (+3.0R win, -0.5R loss).
    Expected: is_robust = True across all 8 TP/SL shift scenarios, max_drop <= 50%.
    """
    np.random.seed(42)
    trades = generate_robust_wide_sl_tp_dataset(n=40)

    is_robust, detail = EdgeDiscoveryEngine._evaluate_robustness(trades)

    assert is_robust is True, "Robust wide SL/TP dataset must pass robustness test"
    assert len(detail["scenarios"]) == 8, "Must evaluate exactly 8 shift scenarios (±5%, ±10% TP/SL)"
    assert detail["all_scenarios_positive"] is True, "All 8 scenarios must maintain positive expectancy"
    assert detail["max_drop_pct"] <= 50.0, f"Max expectancy drop ({detail['max_drop_pct']}%) must be <= 50%"


def test_evaluate_robustness_structure():
    """
    Verifies that robustness detail structure contains expected shift scenario metadata.
    """
    np.random.seed(42)
    trades = generate_robust_wide_sl_tp_dataset(n=20)

    is_robust, detail = EdgeDiscoveryEngine._evaluate_robustness(trades)

    scenario_keys = [s["scenario"] for s in detail["scenarios"]]
    assert "TP +5%" in scenario_keys
    assert "TP -10%" in scenario_keys
    assert "SL +10%" in scenario_keys
    assert "SL -5%" in scenario_keys


def test_evaluate_robustness_mode_field_present():
    """
    Verifies that the new `mode`, `price_action_count`, and
    `simple_mode_fallback_count` fields are present in robustness_detail.
    Without mfe_price/mae_price in trade dicts, mode must be 'simple_mode'.
    """
    np.random.seed(42)
    trades = generate_robust_wide_sl_tp_dataset(n=20)

    _, detail = EdgeDiscoveryEngine._evaluate_robustness(trades)

    assert "mode" in detail, "robustness_detail must contain 'mode' field"
    assert "price_action_count" in detail, "robustness_detail must contain 'price_action_count'"
    assert "simple_mode_fallback_count" in detail, "robustness_detail must contain 'simple_mode_fallback_count'"
    # Without any mfe/mae, mode must be simple_mode
    assert detail["mode"] == "simple_mode", (
        f"Without mfe/mae data, mode must be 'simple_mode', got '{detail['mode']}'"
    )
    assert detail["price_action_count"] == 0
    assert detail["simple_mode_fallback_count"] > 0


def test_price_action_mode_diverges_from_simple_mode():
    """
    CRITICAL: proves that price-action mode produces DIFFERENT results from
    simple mode for trades where the shifted TP level was never actually reached.

    Scenario: 20 LONG trades, all marked exit_reason='take_profit', entry=100,
    sl=95, tp=110. These trades use Simple Mode → assume TP+10% (= 121) was
    reached → r_shifted = (121-100)/5 = 4.2R.

    With price-action mode: mfe_price = 108 (price only moved to 108, NOT 121).
    TP+10% level = entry + (tp-entry)*1.1 = 100 + 11 = 111. mfe=108 < 111 → TP
    was NOT reached. mae_price = 97 (did not breach SL=95). SL-10% level =
    entry - (entry-sl)*1.1 = 100 - 5.5 = 94.5. mae=97 > 94.5 → SL not hit.
    Result: neither level reached → r_shifted = r_orig = 2.0R.

    This demonstrates that Simple Mode OVERESTIMATES the robustness score here
    (4.2R shifted vs 2.0R actual), and price-action mode gives the correct answer.
    """
    entry_p = 100.0
    sl_p = 95.0
    tp_p = 110.0
    risk_dist = entry_p - sl_p          # 5.0
    orig_rr = (tp_p - entry_p) / risk_dist  # 2.0R

    # MFE = 108 (not enough to reach any shifted TP >= 110)
    # MAE = 97  (not enough to breach any shifted SL <= 95)
    trades_with_pa = [
        {
            "id": f"trade-{i}",
            "r_realized": orig_rr,
            "rr_realized": orig_rr,
            "entry_time": None,
            "exit_reason": "take_profit",
            "entry_price": entry_p,
            "stop_loss": sl_p,
            "take_profit": tp_p,
            "direction": "LONG",
            "mfe_price": 108.0,   # below any TP+5%/+10% level
            "mae_price": 97.0,    # above any SL-5%/-10% level
        }
        for i in range(20)
    ]

    # Build exec_map directly (as if it came from the DB query in _evaluate_robustness)
    trades_no_pa = [
        {k: v for k, v in t.items() if k not in ("mfe_price", "mae_price")}
        for t in trades_with_pa
    ]
    # Add None mfe/mae explicitly to simulate missing data
    for t in trades_no_pa:
        t["mfe_price"] = None
        t["mae_price"] = None

    # Run with PA data
    _, detail_pa = EdgeDiscoveryEngine._evaluate_robustness(trades_with_pa)
    # Run without PA data (simple mode)
    _, detail_sm = EdgeDiscoveryEngine._evaluate_robustness(trades_no_pa)

    assert detail_pa["mode"] == "price_action", (
        f"All trades have mfe/mae → mode should be 'price_action', got '{detail_pa['mode']}'"
    )
    assert detail_sm["mode"] == "simple_mode", (
        f"No mfe/mae → mode should be 'simple_mode', got '{detail_sm['mode']}'"
    )

    # Get TP+10% scenario result from each
    pa_tp10 = next(s for s in detail_pa["scenarios"] if s["scenario"] == "TP +10%")
    sm_tp10 = next(s for s in detail_sm["scenarios"] if s["scenario"] == "TP +10%")

    # Price-action: mfe=108 did not reach shifted TP=111 → r_shifted = r_orig = 2.0R
    assert abs(pa_tp10["expectancy_r"] - orig_rr) < 0.01, (
        f"PA mode: mfe did not reach shifted TP, expected r_orig={orig_rr:.2f}R, "
        f"got {pa_tp10['expectancy_r']:.2f}R"
    )

    # Simple mode: assumes TP hit regardless → r_shifted = (110*1.1-100)/5 = 4.2R
    expected_sm_r = ((tp_p - entry_p) * 1.1) / risk_dist
    assert abs(sm_tp10["expectancy_r"] - expected_sm_r) < 0.01, (
        f"Simple mode: expected r_shifted={expected_sm_r:.2f}R, got {sm_tp10['expectancy_r']:.2f}R"
    )

    # The key assertion: PA and SM produce DIFFERENT results for TP+10%
    assert pa_tp10["expectancy_r"] != sm_tp10["expectancy_r"], (
        "Price-action and simple-mode must diverge when mfe did not reach the shifted TP level"
    )
    assert pa_tp10["expectancy_r"] < sm_tp10["expectancy_r"], (
        "PA mode must be MORE CONSERVATIVE than simple mode when price did not reach shifted TP"
    )


def test_price_action_short_direction_correct():
    """
    Verifies that SHORT direction logic is the mirror of LONG.
    For SHORT: entry=100, sl=105 (above entry), tp=90 (below entry).
    MFE for SHORT = min_low = 88 (price moved down to 88, beyond tp=90).
    MAE for SHORT = max_high = 102 (price moved up to 102, did not reach sl=105).
    TP+10% level for SHORT = 100 - 11 = 89. mfe=88 <= 89 → TP+10% HIT.
    r_shifted = 11 / 5 = 2.2R.
    """
    entry_p = 100.0
    sl_p = 105.0
    tp_p = 90.0
    risk_dist = abs(entry_p - sl_p)   # 5.0
    orig_rr = abs(tp_p - entry_p) / risk_dist  # 2.0R

    trades = [
        {
            "id": f"short-trade-{i}",
            "r_realized": orig_rr,
            "rr_realized": orig_rr,
            "entry_time": None,
            "exit_reason": "take_profit",
            "entry_price": entry_p,
            "stop_loss": sl_p,
            "take_profit": tp_p,
            "direction": "SHORT",
            "mfe_price": 88.0,   # best price for SHORT (min_low) = 88
            "mae_price": 102.0,  # worst price for SHORT (max_high) = 102
        }
        for i in range(20)
    ]

    _, detail = EdgeDiscoveryEngine._evaluate_robustness(trades)

    assert detail["mode"] == "price_action"
    tp10 = next(s for s in detail["scenarios"] if s["scenario"] == "TP +10%")

    # New TP for SHORT at +10% dist: new_tp_dist = (entry-tp)*1.1 = 10*1.1 = 11
    # mfe=88 <= new_tp_price=89 → TP hit → r_shifted = new_tp_dist / risk_dist = 11/5 = 2.2R
    expected_r = abs(tp_p - entry_p) * 1.1 / risk_dist  # 2.2
    assert abs(tp10["expectancy_r"] - expected_r) < 0.05, (
        f"SHORT TP+10%: expected ~{expected_r:.2f}R, got {tp10['expectancy_r']:.2f}R"
    )

