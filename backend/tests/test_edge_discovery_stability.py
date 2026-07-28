import numpy as np
import pytest
from app.services.edge_discovery_engine import EdgeDiscoveryEngine
from tests.fixtures.synthetic_trades import generate_stable_winning_dataset, generate_declining_trend_dataset


def test_evaluate_stability_with_stable_winning_dataset():
    """
    Verifies that _evaluate_stability returns (True, detail) for a chronologically stable dataset.
    Dataset A: 40 trades with 60% win rate (+1.5R win, -1R loss) distributed evenly.
    Expected: mean expectancy > 0 in all 3 periods, CV <= 0.75 -> is_stable = True.
    """
    np.random.seed(42)
    trades = generate_stable_winning_dataset(n=40)
    
    is_stable, detail = EdgeDiscoveryEngine._evaluate_stability(trades)
    
    # Manual verification assertions
    assert is_stable is True, "Dataset A must pass stability test (is_stable=True)"
    assert detail["all_periods_positive"] is True, "All 3 chronological periods must have positive expectancy"
    assert detail["cv"] <= 0.75, f"Coefficient of Variation ({detail['cv']:.2f}) must be <= 0.75"
    assert len(detail["periods"]) == 3, "Detail must contain exactly 3 chronological periods"


def test_evaluate_stability_with_declining_trend_dataset():
    """
    Verifies that _evaluate_stability returns (False, detail) for a dataset with severe performance degradation.
    Dataset B: 40 trades where late period performance drops to negative expectancy (-0.8R).
    Expected: is_stable = False due to period 3 negative expectancy or high CV > 0.75.
    """
    np.random.seed(42)
    trades = generate_declining_trend_dataset(n=40)
    
    is_stable, detail = EdgeDiscoveryEngine._evaluate_stability(trades)
    
    # Manual verification assertions
    assert is_stable is False, "Dataset B with declining trend must fail stability test (is_stable=False)"
    assert detail["all_periods_positive"] is False or detail["cv"] > 0.75, "Must fail either due to negative period expectancy or high CV"
