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
