import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.models import Trade, ExchangeFill, TradeFill, APICredential
from app.tasks.worker import poll_open_positions

class TestBinanceSync(unittest.TestCase):
    
    def setUp(self):
        self.db = SessionLocal()
        # Ensure we have a mock API credential record so the task doesn't skip
        cred = self.db.query(APICredential).filter(APICredential.service_name == "binance").first()
        if not cred:
            cred = APICredential(
                service_name="binance",
                encrypted_api_key="mock",
                encrypted_api_secret="mock"
            )
            self.db.add(cred)
            self.db.commit()
            
        # Clean up any active test trades
        self.db.query(Trade).filter(Trade.pair == "BTCUSDT").delete()
        self.db.commit()

    def tearDown(self):
        self.db.query(Trade).filter(Trade.pair == "BTCUSDT").delete()
        self.db.commit()
        self.db.close()

    @patch("app.services.binance.BinanceService.get_position_risk")
    @patch("app.services.binance.BinanceService.get_user_trades")
    @patch("app.services.binance.BinanceService.get_open_orders")
    def test_sync_flow_open_and_close(self, mock_get_open_orders, mock_get_user_trades, mock_get_position_risk):
        # 1. Mocking Position Open (Active Long Position)
        mock_get_position_risk.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.010",  # Long
                "entryPrice": "60000.00",
                "leverage": "10",
                "updateTime": 1784558800000
            }
        ]
        
        # Mock entry fills
        mock_get_user_trades.return_value = [
            {
                "id": 999991,
                "orderId": 888881,
                "price": "60000.00",
                "qty": "0.010",
                "commission": "0.05",
                "commissionAsset": "USDT",
                "realizedPnl": "0.0",
                "side": "BUY",
                "time": 1784558800000
            }
        ]
        
        # Mock open orders (Stop Loss at 59000, Take Profit at 62000)
        mock_get_open_orders.return_value = [
            {
                "type": "STOP_MARKET",
                "stopPrice": "59000.00"
            },
            {
                "type": "TAKE_PROFIT_MARKET",
                "stopPrice": "62000.00"
            }
        ]
        
        # Run periodic poll task
        result = poll_open_positions()
        self.assertEqual(result, "success")
        
        # Verify Trade record is created in DB
        trade = self.db.query(Trade).filter(Trade.pair == "BTCUSDT", Trade.exit_time == None).first()
        self.assertIsNotNone(trade)
        self.assertEqual(trade.direction, "long")
        self.assertEqual(float(trade.entry_price), 60000.0)
        self.assertEqual(float(trade.stop_loss), 59000.0)
        self.assertEqual(float(trade.take_profit), 62000.0)
        self.assertEqual(float(trade.leverage), 10.0)
        self.assertEqual(float(trade.margin), 60.0)  # qty (0.01) * price (60000) / lev (10) = 60
        
        # Verify entry fills linked
        fills = self.db.query(TradeFill).filter(TradeFill.trade_id == trade.id, TradeFill.role == "entry").all()
        self.assertEqual(len(fills), 1)
        self.assertEqual(float(fills[0].exchange_fill.price), 60000.0)
        self.assertEqual(fills[0].exchange_fill.side, "BUY")

        # 2. Mocking Position Close (Position is gone)
        mock_get_position_risk.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.0",  # Closed
                "entryPrice": "0.0",
                "leverage": "10",
                "updateTime": 1784558900000
            }
        ]
        
        # Mock exit fills (closed at 61000, realized PnL = +10 USDT)
        mock_get_user_trades.return_value = [
            {
                "id": 999992,
                "orderId": 888882,
                "price": "61000.00",
                "qty": "0.010",
                "commission": "0.05",
                "commissionAsset": "USDT",
                "realizedPnl": "10.00",
                "side": "SELL",
                "time": 1784558900000
            }
        ]
        
        # Run periodic poll task again
        result = poll_open_positions()
        self.assertEqual(result, "success")
        
        # Verify Trade record is updated as closed
        self.db.commit()
        closed_trade = self.db.query(Trade).filter(Trade.id == trade.id).first()
        self.assertIsNotNone(closed_trade.exit_time)
        self.assertEqual(float(closed_trade.exit_price), 61000.0)
        self.assertEqual(float(closed_trade.pnl), 10.0)
        self.assertEqual(float(closed_trade.fee), 0.10)  # 0.05 entry + 0.05 exit

if __name__ == "__main__":
    unittest.main()
