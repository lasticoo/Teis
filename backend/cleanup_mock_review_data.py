from app.database import SessionLocal
from app.models.models import Trade, Psychology, MarketContext, TradeExecution

def cleanup_mock_data():
    db = SessionLocal()
    print("🧹 Menghapus seluruh Data Mock Trade dari database...")
    mock_ids = ["MOCK-WEEKLY-TRADE-001", "MOCK-WEEKLY-TRADE-002", "MOCK-WEEKLY-TRADE-003", "MOCK-TEST-TRADE-999"]
    
    for m_id in mock_ids:
        db.query(Psychology).filter(Psychology.trade_id == m_id).delete()
        db.query(MarketContext).filter(MarketContext.trade_id == m_id).delete()
        db.query(TradeExecution).filter(TradeExecution.trade_id == m_id).delete()
        db.query(Trade).filter(Trade.id == m_id).delete()
    
    db.commit()
    print("✅ BERHASIL: Seluruh Data Mock telah dihapus dari database. Sistem kembali bersih 100%!")
    db.close()

if __name__ == "__main__":
    cleanup_mock_data()
