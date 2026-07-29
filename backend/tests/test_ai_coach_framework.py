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
        "historical_similar_setup": {"sample_size": 10, "win_rate_pct": 60.0, "avg_rr": 2.5, "expectancy_r": 1.1, "is_statistically_significant": False},
        "screenshots": [],
        "equity_growth": {"equity_phase": "STABLE_BASELINE", "cumulative_r_trajectory": 0.0, "daily_progression_str": "No trades"}
    }

    # 1. Test Prompt Tuple
    prompt, img_payloads = AICoachService._build_prompt(dummy_data)
    assert isinstance(prompt, str)
    assert isinstance(img_payloads, list)
    assert "PERSPEKTIF MENTOR & CARA BERPIKIR TRADER PROFESIONAL" in prompt
    assert "INSPEKSI CHART VISUAL BEFORE ENTRY & AFTER EXIT" in prompt
    assert "Mengapa Analisis Salah" in prompt
    assert "Prinsip SMC yang Dilanggar" in prompt
    assert "Apa yang Seharusnya Dilihat Terlebih Dahulu" in prompt
    assert "Apa yang Dilihat Trader Berpengalaman tetapi Terlewatkan" in prompt
    assert "Pelajaran Terbesar" in prompt
    assert "Rapor Penilaian Mentor (Skala 1–10)" in prompt
    assert "Kriteria Evaluasi" in prompt
    assert "Klasifikasi Tier Setup & Alasan Penilaian" in prompt
    assert "Saran Konkret & Langkah Perbaikan Ke Depannya" in prompt
    assert "[A+ Setup / A Setup / B Setup / C Setup]" in prompt

    # Sample size caveat
    assert "PERHATIAN STATISTIK" in prompt
    assert "TERLALU KECIL" in prompt

    # 2. Test Fallback Review Output
    fallback = AICoachService._generate_analytic_fallback_review(dummy_data)
    assert "Saran Konkret & Langkah Perbaikan Ke Depannya" in fallback
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


def test_fallback_honest_chart_disclaimer_when_screenshots_present():
    dummy_data = {
        "symbol_pair": "ETHUSDT",
        "direction": "SHORT",
        "outcome": "WIN",
        "entry_price": 3000.0,
        "exit_price": 2900.0,
        "stop_loss": 3050.0,
        "take_profit": 2900.0,
        "rr_planned": 2.0,
        "rr_realized": 2.0,
        "pnl": 100.0,
        "fee": 0.5,
        "holding_time_minutes": 120,
        "exit_reason": "take_profit",
        "execution_details": {"order_type": "limit", "moved_to_breakeven": False, "trailing_stop_used": False},
        "setup_tags": ["Order Block (H4)"],
        "market_context": {"trend_htf": "bearish", "trend_ltf": "bearish", "session": "ny", "fear_greed_index": 50, "btc_dominance": 54.0},
        "psychology": {"confidence_level": 8, "plan_adherence": True, "psychological_tags": [], "free_notes": "Disiplin"},
        "historical_similar_setup": {"sample_size": 25, "win_rate_pct": 68.0, "avg_rr": 2.2, "expectancy_r": 1.5, "is_statistically_significant": True},
        "screenshots": [{"stage": "before_entry_4h", "url": "http://localhost:9000/teis-screenshots/test.webp"}],
        "equity_growth": {"equity_phase": "CONSISTENT_GROWTH", "cumulative_r_trajectory": 5.0, "daily_progression_str": "Stable"}
    }

    fallback = AICoachService._generate_analytic_fallback_review(dummy_data)
    assert "tidak bisa membaca gambar secara visual" in fallback
    assert "bukan validasi visual order block/FVG" in fallback
    assert "Konfluensi visual mengonfirmasi" not in fallback


def test_weekly_review_sample_size_thresholds(mocker):
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
    assert "Rapor Penilaian Mingguan Mentor (Skala 1–10)" in markdown
    assert "Klasifikasi Tier Setup Dominan Mingguan & Alasan Penilaian" in markdown
    assert "C Setup" in markdown
