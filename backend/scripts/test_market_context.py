import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import Trade, MarketContext
from app.tasks.worker import collect_market_context

# Set up SQLite in-memory database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
TRADE_ID = "test-trade-market-ctx-9999"


class TestMarketContextCollection(unittest.TestCase):
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

        trade = Trade(
            id=TRADE_ID,
            pair="BTCUSDT",
            direction="long",
            entry_price=Decimal("60000.00"),
            entry_time=datetime.now(),
            data_source="binance_sync",
        )
        self.db.add(trade)
        self.db.commit()
        # Expunge so the task's own session manages the object cleanly
        self.db.expunge_all()

    def tearDown(self):
        self.db.close()

    @patch("app.tasks.worker.redis.Redis")
    @patch("app.tasks.worker.requests.get")
    @patch("app.services.binance.BinanceService.get_client")
    @patch("app.tasks.worker.SessionLocal")
    def test_collect_market_context_success(
        self, mock_session_local, mock_get_client, mock_requests_get, mock_redis
    ):
        """Task harus berhasil menyimpan semua indikator ke tabel market_context."""
        # Redirect SessionLocal ke in-memory SQLite session kita
        mock_session_local.return_value = self.db

        # Mock Redis — cache miss agar API eksternal dipanggil
        mock_r = MagicMock()
        mock_redis.return_value = mock_r
        mock_r.get.return_value = None

        # Mock CoinGecko
        mock_res_gecko = MagicMock()
        mock_res_gecko.status_code = 200
        mock_res_gecko.json.return_value = {
            "data": {"market_cap_percentage": {"btc": 54.32}}
        }

        # Mock Alternative.me
        mock_res_fgi = MagicMock()
        mock_res_fgi.status_code = 200
        mock_res_fgi.json.return_value = {"data": [{"value": "78"}]}

        def mock_get(url, *args, **kwargs):
            if "coingecko" in url:
                return mock_res_gecko
            elif "alternative.me" in url:
                return mock_res_fgi
            return MagicMock()

        mock_requests_get.side_effect = mock_get

        # Mock Binance client
        mock_binance = MagicMock()
        mock_get_client.return_value = mock_binance

        # Candle: [OpenTime, Open, High, Low, Close, Volume, CloseTime, ...]
        mock_candle = [
            1700000000000, "60000.0", "61000.0", "59000.0", "60000.0",
            "10.0", 1700000060000, "600000.0", 100, "5.0", "300000.0", "0",
        ]
        mock_binance.futures_klines.return_value = [mock_candle] * 60
        mock_binance.futures_ticker.return_value = {"quoteVolume": "1500000000.00"}
        mock_binance.futures_open_interest_hist.return_value = [
            {"sumOpenInterestValue": "3500000.00"}
        ]
        mock_binance.futures_funding_rate.return_value = [{"fundingRate": "0.000100"}]

        # Jalankan task secara sinkron
        result = collect_market_context(TRADE_ID)
        self.assertEqual(result, "success")

        # Verifikasi data tersimpan di DB
        ctx = self.db.query(MarketContext).filter(
            MarketContext.trade_id == TRADE_ID
        ).first()
        self.assertIsNotNone(ctx, "Record market_context harus terbuat di DB")
        self.assertIn(ctx.trend_htf, ["bull", "bear", "range"])
        self.assertIn(ctx.trend_ltf, ["bull", "bear", "range"])
        self.assertAlmostEqual(float(ctx.volume_24h), 1_500_000_000.0, places=0)
        self.assertAlmostEqual(float(ctx.open_interest), 3_500_000.0, places=0)
        self.assertAlmostEqual(float(ctx.funding_rate), 0.0001, places=6)
        self.assertAlmostEqual(float(ctx.btc_dominance), 54.32, places=2)
        self.assertEqual(ctx.fear_greed_index, 78)

        # Verifikasi caching Redis terpanggil dengan argumen yang benar
        mock_r.setex.assert_any_call("btc_dominance", 3600, "54.32")
        mock_r.setex.assert_any_call("fear_greed_index", 3600, "78")

    @patch("app.tasks.worker.redis.Redis")
    @patch("app.tasks.worker.requests.get")
    @patch("app.services.binance.BinanceService.get_client")
    @patch("app.tasks.worker.SessionLocal")
    def test_collect_market_context_trade_not_found(
        self, mock_session_local, mock_get_client, mock_requests_get, mock_redis
    ):
        """Task harus mengembalikan 'failed_not_found' jika trade_id tidak ada di DB."""
        mock_session_local.return_value = self.db
        result = collect_market_context("non-existent-trade-id-0000")
        self.assertEqual(result, "failed_not_found")


if __name__ == "__main__":
    unittest.main(verbosity=2)
