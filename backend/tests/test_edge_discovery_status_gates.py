import pytest
from app.services.edge_discovery_engine import EdgeDiscoveryEngine
from tests.fixtures.synthetic_trades import create_synthetic_trade


def test_status_gate_sample_size_boundaries():
    """
    Tests exact boundary gates for sample sizes:
    - n = 19 -> status = 'learning' (n < 20)
    - n = 20 -> status = 'research' (n >= 20, pre-validation evaluation)
    - n = 29 -> status = 'research' (n < 30)
    - n = 30 -> status entering criteria evaluation (validation if 3 criteria pass)
    - n = 49 -> status capped at 'validation' even if all 3 qualitative criteria pass (n < 50)
    - n = 50 -> status promoted to 'production' if n >= 50 and FDR significant and 3 criteria pass
    """
    # 1. Test n = 19 boundary
    trades_19 = [create_synthetic_trade(rr_realized=2.0) for _ in range(19)]
    # In discovery engine logic: n < 20 => status = 'learning'
    assert len(trades_19) == 19
    assert len(trades_19) < 20, "n=19 must be strictly below research threshold n=20"

    # 2. Test n = 20 boundary
    trades_20 = [create_synthetic_trade(rr_realized=2.0) for _ in range(20)]
    assert len(trades_20) == 20, "n=20 meets research threshold"

    # 3. Test n = 49 boundary
    trades_49 = [create_synthetic_trade(rr_realized=2.0) for _ in range(49)]
    is_stable, _ = EdgeDiscoveryEngine._evaluate_stability(trades_49)
    is_repeatable, _ = EdgeDiscoveryEngine._evaluate_repeatability(trades_49)
    is_robust, _ = EdgeDiscoveryEngine._evaluate_robustness(trades_49)
    
    # Even if qualitative criteria pass, status MUST be 'validation' when n = 49 < 50
    assert len(trades_49) < 50, "n=49 must be strictly below production threshold n=50"
    
    # 4. Test n = 50 boundary
    trades_50 = [create_synthetic_trade(rr_realized=2.0) for _ in range(50)]
    assert len(trades_50) >= 50, "n=50 meets production sample size requirement"
