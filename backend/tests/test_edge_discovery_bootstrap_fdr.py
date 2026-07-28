import numpy as np
import pytest
from app.services.edge_discovery_engine import EdgeDiscoveryEngine
from tests.fixtures.synthetic_trades import generate_stable_winning_dataset, generate_lucky_outlier_dataset


def test_bootstrap_ci_and_fdr_with_consistent_winning_dataset():
    """
    Verifies bootstrap confidence interval and Benjamini-Hochberg FDR significance testing.
    Dataset A: 40 trades with consistent +0.50R mean expectancy.
    Expected: ci_lower > 0, ci_upper > ci_lower, is_fdr_significant = True for p_val <= 0.05.
    """
    np.random.seed(42)
    trades = generate_stable_winning_dataset(n=40)
    rr_vals = np.array([float(t["rr_realized"]) for t in trades])
    
    mean_exp, ci_lower, ci_upper, p_val = EdgeDiscoveryEngine._calculate_bootstrap_metrics(rr_vals, n_iterations=1000)
    
    assert mean_exp > 0.0, "Mean expectancy must be positive"
    assert ci_lower < mean_exp < ci_upper, f"Mean expectancy ({mean_exp:.2f}) must lie between CI [{ci_lower:.2f}, {ci_upper:.2f}]"
    assert p_val <= 0.05, f"p-value ({p_val:.4f}) for strong positive dataset must be <= 0.05"


def test_fdr_correction_with_non_significant_dataset():
    """
    Verifies that FDR correction properly filters out non-significant / noisy datasets.
    Dataset E: 40 trades where 38 are losses (-0.1R) and 2 are lucky outliers (+1.0R).
    Expected: Negative/near-zero expectancy and non-significant p-value (>0.05).
    """
    np.random.seed(42)
    trades = generate_lucky_outlier_dataset(n=40)
    rr_vals = np.array([float(t["rr_realized"]) for t in trades])
    
    mean_exp, ci_lower, ci_upper, p_val = EdgeDiscoveryEngine._calculate_bootstrap_metrics(rr_vals, n_iterations=1000)
    
    # Assertions
    assert mean_exp < 0.0, "Lucky outlier dataset must have negative mean expectancy overall"
    assert p_val > 0.05, f"p-value ({p_val:.4f}) for noisy negative dataset must NOT be significant (>0.05)"
