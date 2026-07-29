import pytest
from datetime import datetime, timedelta
from app.services.ai_coach_service import AICoachService

def test_single_trade_prompt_contains_all_mentor_framework_elements():
    dummy_data = {
        "symbol_pair": "BTCUSDT",
        "direction": "LONG",
        "outcome": "LOSS",
        "entry_price": 50000.0,
        "exit_price": 49500.0,
        "stop_loss": 49500.0,
        "take_profit": 52000.0,
        "rr_planned": 4.0,
        "rr_realized": -1.0,
        "pnl": -50.0,
        "fee": 0.5,
        "holding_time_minutes": 45,
        "exit_reason": "stop_loss",
        "execution_details": {"order_type": "limit", "moved_to_breakeven": False, "trailing_stop_used": False},
        "setup_tags": ["Order Block (H4)", "FVG (H1)"],
        "market_context": {"trend_htf": "bullish", "trend_ltf": "bearish", "session": "london", "fear_greed_index": 65, "btc_dominance": 54.5},
        "psychology": {"confidence_level": 7, "plan_adherence": False, "psychological_tags": ["FOMO"], "free_notes": "Entry impulsif"},
        "historical_similar_setup": {"sample_size": 10, "win_rate_pct": 60.0, "avg_rr": 2.5, "expectancy_r": 1.1},
        "screenshots": [],
        "equity_growth": {"equity_phase": "STABLE_BASELINE", "cumulative_r_trajectory": 0.0, "daily_progression_str": "No trades"}
    }

    # 1. Test Prompt String
    prompt = AICoachService._build_prompt(dummy_data)
    assert "PERSPEKTIF MENTOR & CARA BERPIKIR TRADER PROFESIONAL" in prompt
    assert "Mengapa Analisis Salah" in prompt
    assert "Prinsip SMC yang Dilanggar" in prompt
    assert "Apa yang Seharusnya Dilihat Terlebih Dahulu" in prompt
    assert "Apa yang Dilihat Trader Berpengalaman tetapi Terlewatkan" in prompt
    assert "Pelajaran Terbesar" in prompt
    assert "Rapor Penilaian Mentor (Skala 1–10)" in prompt
    assert "Market Structure:" in prompt
    assert "Liquidity Reading:" in prompt
    assert "Bias:" in prompt
    assert "Entry Timing:" in prompt
    assert "Risk Management:" in prompt
    assert "Keseluruhan Kualitas Setup:" in prompt
    assert "Klasifikasi Tier Setup & Alasan Penilaian" in prompt
    assert "[A+ Setup / A Setup / B Setup / C Setup]" in prompt

    # 2. Test Fallback Review Output
    fallback = AICoachService._generate_analytic_fallback_review(dummy_data)
    assert "Refleksi Cara Berpikir Trader Profesional (5 Pertanyaan Kunci Mentor)" in fallback
    assert "Mengapa Analisis Salah" in fallback
    assert "Prinsip SMC yang Dilanggar" in fallback
    assert "Apa yang Seharusnya Dilihat Terlebih Dahulu" in fallback
    assert "Apa yang Dilihat Trader Berpengalaman tetapi Terlewatkan" in fallback
    assert "Satu Pelajaran Terbesar" in fallback
    assert "Rapor Penilaian Mentor (Skala 1–10)" in fallback
    assert "Market Structure" in fallback
    assert "Liquidity Reading" in fallback
    assert "Bias" in fallback
    assert "Entry Timing" in fallback
    assert "Risk Management" in fallback
    assert "Keseluruhan Kualitas Setup" in fallback
    assert "Klasifikasi Tier Setup & Alasan Penilaian" in fallback
    assert "C Setup" in fallback  # Plan Adherence was False -> C Setup


def test_weekly_review_prompt_and_fallback_contain_framework_elements(mocker):
    # Mock LLM call to force fallback for testing markdown structure
    mocker.patch.object(AICoachService, "_call_llm_provider", return_value="")
    
    mock_db = mocker.MagicMock()
    mock_db.query().filter().all.return_value = []

    start = "2026-07-20"
    end = "2026-07-27"
    
    markdown = AICoachService._build_weekly_review_markdown(
        db=mock_db,
        start_date=start,
        end_date=end,
        total_trades=5,
        win_rate=40.0,
        total_pnl=-20.0,
        total_r=-1.0,
        adherence_pct=60.0,
        top_tags_str="FOMO (2x)",
        trades=[]
    )

    assert "Refleksi Cara Berpikir Trader Profesional Mingguan (5 Evaluasi Kunci Mentor)" in markdown
    assert "Mengapa Analisis/Pendekatan Salah" in markdown
    assert "Prinsip SMC yang Paling Sering Dilanggar Minggu Ini" in markdown
    assert "Apa yang Seharusnya Dilihat Terlebih Dahulu" in markdown
    assert "Apa yang Dilihat Trader Berpengalaman tetapi Terlewatkan" in markdown
    assert "Satu Pelajaran Terbesar Minggu Ini" in markdown
    assert "Rapor Penilaian Mingguan Mentor (Skala 1–10)" in markdown
    assert "Market Structure" in markdown
    assert "Liquidity Reading" in markdown
    assert "Bias" in markdown
    assert "Entry Timing" in markdown
    assert "Risk Management" in markdown
    assert "Keseluruhan Kualitas Setup Mingguan" in markdown
    assert "Klasifikasi Tier Setup Dominan Mingguan & Alasan Penilaian" in markdown
    assert "C Setup" in markdown  # Adherence < 70% -> C Setup
