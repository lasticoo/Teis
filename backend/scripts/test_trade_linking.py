import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import Trade, ExchangeFill, TradeFill
from app.services.trade_collection import TradeCollectionService, DEFAULT_RISK_AMOUNT

TEST_DATABASE_URL = "sqlite:///:memory:"


class TestTradeCollectionAndLinking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=cls.engine)

    def setUp(self):
        self.db = self.TestingSessionLocal()
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self):
        self.db.close()

    def test_calculate_vwap_multi_fills(self):
        """Uji perhitungan VWAP presisi Decimal untuk multiple fills entry."""
        # Fills: 100 qty @ $10.00 ($1000) + 200 qty @ $13.00 ($2600) => Total 300 qty, Total $3600 => VWAP = $12.00
        fill1 = ExchangeFill(
            id="f1", symbol="BTCUSDT", binance_trade_id=1, binance_order_id=101,
            price=Decimal("10.00"), qty=Decimal("100.00"), fee=Decimal("0.50"),
            side="BUY", executed_at=datetime.now()
        )
        fill2 = ExchangeFill(
            id="f2", symbol="BTCUSDT", binance_trade_id=2, binance_order_id=102,
            price=Decimal("13.00"), qty=Decimal("200.00"), fee=Decimal("1.00"),
            side="BUY", executed_at=datetime.now()
        )

        vwap, total_qty = TradeCollectionService.calculate_vwap([fill1, fill2])
        self.assertEqual(vwap, Decimal("12.00"))
        self.assertEqual(total_qty, Decimal("300.00"))

    def test_calculate_financials_net_pnl_and_rr(self):
        """Uji perhitungan PnL bersih, komisi fee, dan Realized RR."""
        trade = Trade(
            id="t-100",
            pair="BTCUSDT",
            direction="long",
            entry_price=Decimal("60000.00"),
            entry_time=datetime.now() - timedelta(minutes=30),
            risk_amount=Decimal("100.00"),
            data_source="binance_sync"
        )

        entry_fill = ExchangeFill(
            id="ef-1", symbol="BTCUSDT", binance_trade_id=10, binance_order_id=201,
            price=Decimal("60000.00"), qty=Decimal("1.00"), fee=Decimal("6.00"),
            side="BUY", executed_at=trade.entry_time
        )
        
        exit_fill = ExchangeFill(
            id="ef-2", symbol="BTCUSDT", binance_trade_id=11, binance_order_id=202,
            price=Decimal("60500.00"), qty=Decimal("1.00"), fee=Decimal("6.05"),
            side="SELL", executed_at=datetime.now(),
            raw_payload={"realizedPnl": "500.00"}
        )

        financials = TradeCollectionService.calculate_financials(trade, [entry_fill], [exit_fill])

        # Gross PnL = 500.00, Fee = 6.00 + 6.05 = 12.05 => Net PnL = 487.95
        self.assertEqual(financials["gross_pnl"], Decimal("500.00"))
        self.assertEqual(financials["total_fee"], Decimal("12.05"))
        self.assertEqual(financials["net_pnl"], Decimal("487.95"))
        # Realized RR = 487.95 / 100.00 = 4.88
        self.assertEqual(financials["rr_realized"], Decimal("4.88"))

    def test_zero_risk_amount_fallback(self):
        """Uji fallback DEFAULT_RISK_AMOUNT jika risk_amount adalah 0 atau None untuk mencegah pembagian nol."""
        trade_zero_risk = Trade(
            id="t-200",
            pair="ETHUSDT",
            direction="long",
            entry_price=Decimal("3000.00"),
            entry_time=datetime.now(),
            risk_amount=Decimal("0.0"),
            data_source="binance_sync"
        )

        entry_fill = ExchangeFill(
            id="f-3", symbol="ETHUSDT", binance_trade_id=30, binance_order_id=301,
            price=Decimal("3000.00"), qty=Decimal("1.00"), fee=Decimal("1.00"),
            side="BUY", executed_at=trade_zero_risk.entry_time
        )
        exit_fill = ExchangeFill(
            id="f-4", symbol="ETHUSDT", binance_trade_id=31, binance_order_id=302,
            price=Decimal("3050.00"), qty=Decimal("1.00"), fee=Decimal("1.00"),
            side="SELL", executed_at=datetime.now(),
            raw_payload={"realizedPnl": "50.00"}
        )

        financials = TradeCollectionService.calculate_financials(trade_zero_risk, [entry_fill], [exit_fill])
        
        # Risk amount fallback to DEFAULT_RISK_AMOUNT (10.0)
        self.assertEqual(financials["risk_amount"], DEFAULT_RISK_AMOUNT)
        # Net PnL = 50.00 - 2.00 = 48.00 => RR = 48.00 / 10.0 = 4.8
        self.assertEqual(financials["rr_realized"], Decimal("4.8"))

    def test_link_trade_fills_db(self):
        """Uji penggabungan lengkap ke database MySQL/SQLite."""
        trade = Trade(
            id="t-300",
            pair="SOLUSDT",
            direction="long",
            entry_price=Decimal("150.00"),
            entry_time=datetime.now() - timedelta(minutes=15),
            risk_amount=Decimal("20.00"),
            data_source="binance_sync"
        )
        self.db.add(trade)

        ef1 = ExchangeFill(
            id="ef-sol-1", symbol="SOLUSDT", binance_trade_id=50, binance_order_id=501,
            price=Decimal("150.00"), qty=Decimal("10.00"), fee=Decimal("0.50"),
            side="BUY", executed_at=trade.entry_time
        )
        ef2 = ExchangeFill(
            id="ef-sol-2", symbol="SOLUSDT", binance_trade_id=51, binance_order_id=502,
            price=Decimal("160.00"), qty=Decimal("10.00"), fee=Decimal("0.55"),
            side="SELL", executed_at=datetime.now(),
            raw_payload={"realizedPnl": "100.00"}
        )
        self.db.add_all([ef1, ef2])
        self.db.flush()

        tf1 = TradeFill(trade_id=trade.id, exchange_fill_id=ef1.id, role="entry")
        tf2 = TradeFill(trade_id=trade.id, exchange_fill_id=ef2.id, role="exit")
        self.db.add_all([tf1, tf2])
        self.db.commit()

        # Execute link service
        res = TradeCollectionService.link_trade_fills(self.db, trade.id)
        self.assertEqual(res["status"], "success")

        # Verify DB updates
        updated_trade = self.db.query(Trade).filter(Trade.id == trade.id).first()
        self.assertEqual(float(updated_trade.entry_price), 150.0)
        self.assertEqual(float(updated_trade.exit_price), 160.0)
        # Net PnL = 100.00 - (0.50 + 0.55) = 98.95
        self.assertEqual(float(updated_trade.pnl), 98.95)
        # Realized RR = 98.95 / 20.00 = 4.95
        self.assertEqual(float(updated_trade.rr_realized), 4.95)


if __name__ == "__main__":
    unittest.main(verbosity=2)
