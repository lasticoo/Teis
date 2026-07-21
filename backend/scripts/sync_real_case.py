import os
import sys
from decimal import Decimal
from datetime import datetime, timezone

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.models import APICredential, Trade, ExchangeFill, TradeFill
from app.services.binance import BinanceService
from app.tasks.worker import poll_open_positions

def main():
    print("=" * 60)
    print(" SINKRONISASI BINANCE FUTURES - REAL DATA TEST ")
    print("=" * 60)

    db = SessionLocal()
    try:
        # Check database API key
        cred = db.query(APICredential).filter(APICredential.service_name == "binance").first()
        if not cred:
            print("Error: Kunci API Binance belum disimpan di database.")
            print("Silakan simpan terlebih dahulu via halaman Settings di http://localhost:5173/settings")
            sys.exit(1)

        print("✔ Kredensial API ditemukan di database (Tersimpan secara terenkripsi).")
        
        # Test connection
        print("\nMencoba melakukan koneksi ke Binance Futures API...")
        try:
            positions = BinanceService.get_position_risk(db)
            print("✔ Koneksi Sukses!")
        except Exception as e:
            print(f"❌ Koneksi Gagal: {str(e)}")
            print("Periksa kembali API Key / Secret Key Anda, batasan IP di Binance, atau koneksi internet.")
            sys.exit(1)

        # Print all active positions found
        active_positions = []
        for pos in positions:
            amt = float(pos["positionAmt"])
            if amt != 0.0:
                active_positions.append(pos)

        print(f"\nJumlah posisi aktif ditemukan: {len(active_positions)}")
        for pos in active_positions:
            print(f"  - Symbol   : {pos['symbol']}")
            print(f"    Amount   : {pos['positionAmt']}")
            print(f"    Entry Px : {pos['entryPrice']}")
            print(f"    Leverage : {pos.get('leverage', 'N/A')}x")
            print(f"    Mark Px  : {pos['markPrice']}")
            print(f"    Unreal PnL: {pos['unRealizedProfit']} USDT")

        # Run the actual background sync function
        print("\nMenjalankan sinkronisasi database (poll_open_positions) dengan data riil...")
        result = poll_open_positions()
        print(f"✔ Status Eksekusi: {result}")

        # Query database to show changes
        print("\n" + "=" * 60)
        print(" DATA DI DATABASE SETELAH SINKRONISASI ")
        print("=" * 60)
        
        # Fetch active trades
        trades = db.query(Trade).filter(Trade.exit_time == None, Trade.data_source == 'binance_sync').all()
        print(f"Jumlah trade shell aktif di DB: {len(trades)}")
        for t in trades:
            print(f"  - Trade ID : {t.id}")
            print(f"    Pair     : {t.pair}")
            print(f"    Direction: {t.direction.upper()}")
            print(f"    Entry Price: {t.entry_price}")
            print(f"    Leverage : {t.leverage}x")
            print(f"    Stop Loss: {t.stop_loss}")
            print(f"    Take Profit: {t.take_profit}")
            
            # Fetch linked entry fills
            fills = db.query(TradeFill).filter(TradeFill.trade_id == t.id).all()
            print(f"    Jumlah Fills entry terhubung: {len(fills)}")
            for f in fills:
                print(f"      * Fill ID: {f.exchange_fill.binance_trade_id} | Price: {f.exchange_fill.price} | Qty: {f.exchange_fill.qty} | Side: {f.exchange_fill.side}")
        print("=" * 60)

    except Exception as e:
        print(f"Terjadi kesalahan: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
