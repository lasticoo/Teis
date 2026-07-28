import numpy as np
import pytest
from app.services.edge_discovery_engine import EdgeDiscoveryEngine
from tests.fixtures.synthetic_trades import generate_stable_winning_dataset, generate_single_pair_session_dataset


def test_evaluate_repeatability_with_multi_dimension_dataset():
    """
    Verifies that _evaluate_repeatability returns (True, detail) for a dataset with broad coverage.
    Dataset A: 40 trades distributed across multiple pairs, months, and sessions.
    Expected: >50% of valid subgroups (n>=5) have positive expectancy -> is_repeatable = True.
    """
    np.random.seed(42)
    trades = generate_stable_winning_dataset(n=40)
    
    is_repeatable, detail = EdgeDiscoveryEngine._evaluate_repeatability(trades)
    
    assert is_repeatable is True, "Multi-dimension dataset must pass repeatability test"
    assert detail["pct_positive_subgroups"] >= 50.0, f"Percentage of positive subgroups ({detail['pct_positive_subgroups']}%) must be >= 50%"
    assert detail["valid_subgroups"] > 0, "Must have valid subgroups with n>=5"


def test_evaluate_repeatability_with_single_pair_session_dataset():
    """
    Verifies that _evaluate_repeatability flags insufficient subgroup coverage.
    Dataset C: 40 trades confined to 1 pair and 1 session.
    Expected: is_repeatable = False due to lack of multi-subgroup coverage (n<5 for all other subgroups).
    """
    np.random.seed(42)
    trades = generate_single_pair_session_dataset(n=40)
    
    is_repeatable, detail = EdgeDiscoveryEngine._evaluate_repeatability(trades)
    
    # Subgroup coverage assertion
    assert is_repeatable is False, "Single pair/session dataset must fail repeatability test due to lack of subgroup diversity"
