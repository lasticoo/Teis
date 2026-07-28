import uuid
from datetime import datetime
from app.database import SessionLocal
from app.models.models import Trade, Psychology, MarketContext, TradeExecution

def create_mock_data():
    db = SessionLocal()
    print("🚀 Membuat 3 Data Mock Trade untuk Evaluasi Mingguan (27 Jul - 02 Aug 2026)...")

    # Trade 1: BTCUSDT LONG (WIN +3.0R)
    t1_id = "MOCK-WEEKLY-TRADE-001"
    db.query(Psychology).filter(Psychology.trade_id == t1_id).delete()
    db.query(MarketContext).filter(MarketContext.trade_id == t1_id).delete()
    db.query(TradeExecution).filter(TradeExecution.trade_id == t1_id).delete()
    db.query(Trade).filter(Trade.id == t1_id).delete()
    
    t1 = Trade(
        id=t1_id,
        pair="BTCUSDT",
        direction="long",
        entry_price=66200.0,
        exit_price=67800.0,
        stop_loss=65600.0,
        take_profit=67800.0,
        margin=15.0,
        leverage=10.0,
        risk_amount=0.96,
        rr_planned=2.67,
        rr_realized=3.0,
        pnl=2.88,
        fee=0.04,
        entry_time=datetime(2026, 7, 27, 14, 0, 0),
        exit_time=datetime(2026, 7, 27, 18, 30, 0),
        data_source="binance_sync"
    )
    db.add(t1)

    p1 = Psychology(
        trade_id=t1_id,
        confidence_level=9,
        plan_adherence=True,
        psychological_tags=["Sesuai Plan", "Tenang", "Fokus"],
        free_notes="Entry di 4H Bullish Order Block setelah Liquidity Sweep Asia Session."
    )
    db.add(p1)

    # Trade 2: ETHUSDT SHORT (LOSS -1.0R)
    t2_id = "MOCK-WEEKLY-TRADE-002"
    db.query(Psychology).filter(Psychology.trade_id == t2_id).delete()
    db.query(MarketContext).filter(MarketContext.trade_id == t2_id).delete()
    db.query(TradeExecution).filter(TradeExecution.trade_id == t2_id).delete()
    db.query(Trade).filter(Trade.id == t2_id).delete()

    t2 = Trade(
        id=t2_id,
        pair="ETHUSDT",
        direction="short",
        entry_price=3500.0,
        exit_price=3535.0,
        stop_loss=3535.0,
        take_profit=3420.0,
        margin=10.0,
        leverage=10.0,
        risk_amount=0.96,
        rr_planned=2.28,
        rr_realized=-1.0,
        pnl=-0.96,
        fee=0.03,
        entry_time=datetime(2026, 7, 28, 9, 15, 0),
        exit_time=datetime(2026, 7, 28, 10, 45, 0),
        data_source="binance_sync"
    )
    db.add(t2)

    p2 = Psychology(
        trade_id=t2_id,
        confidence_level=7,
        plan_adherence=True,
        psychological_tags=["Sesuai Plan", "Disiplin SL"],
        free_notes="SL tersentuh karena Spike Volatilitas London Open. Proteksi risiko berjalan sempurna."
    )
    db.add(p2)

    # Trade 3: SOLUSDT LONG (WIN +2.5R)
    t3_id = "MOCK-WEEKLY-TRADE-003"
    db.query(Psychology).filter(Psychology.trade_id == t3_id).delete()
    db.query(MarketContext).filter(MarketContext.trade_id == t3_id).delete()
    db.query(TradeExecution).filter(TradeExecution.trade_id == t3_id).delete()
    db.query(Trade).filter(Trade.id == t3_id).delete()

    t3 = Trade(
        id=t3_id,
        pair="SOLUSDT",
        direction="long",
        entry_price=180.0,
        exit_price=190.0,
        stop_loss=176.0,
        take_profit=190.0,
        margin=12.0,
        leverage=10.0,
        risk_amount=0.96,
        rr_planned=2.5,
        rr_realized=2.5,
        pnl=2.40,
        fee=0.03,
        entry_time=datetime(2026, 7, 28, 13, 0, 0),
        exit_time=datetime(2026, 7, 28, 15, 20, 0),
        data_source="binance_sync"
    )
    db.add(t3)

    p3 = Psychology(
        trade_id=t3_id,
        confidence_level=8,
        plan_adherence=True,
        psychological_tags=["Sesuai Plan", "Tenang"],
        free_notes="Target TP 190 tersentuh presisi di 1H FVG mitigation."
    )
    db.add(p3)

    db.commit()
    print("✅ BERHASIL: 3 Data Mock Trade telah ditambahkan ke database!")
    print("   - BTCUSDT (LONG): +3.0R (+$2.88)")
    print("   - ETHUSDT (SHORT): -1.0R (-$0.96)")
    print("   - SOLUSDT (LONG): +2.5R (+$2.40)")
    print("   - Total Minggu Ini: 3 Trade | Win Rate: 66.7% | Total R: +4.50 R | Net PnL: +$4.32")
    db.close()

if __name__ == "__main__":
    create_mock_data()
