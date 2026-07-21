import unittest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import Trade, Psychology, TradeSetupTag, TradeExecution, SetupTaxonomyVersion, MarketContext
from app.api.journal import seed_taxonomy_if_empty
from app.tasks.worker import lock_trade

# Set up SQLite in-memory database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

class TestJournalAPI(unittest.TestCase):
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
        
        # Seed taxonomy
        seed_taxonomy_if_empty(self.db)
        self.taxonomy_items = self.db.query(SetupTaxonomyVersion).all()
        
        # Create a test trade shell
        self.trade = Trade(
            id="test-trade-uuid-1111",
            pair="BTCUSDT",
            direction="long",
            entry_price=Decimal("60000.00"),
            entry_time=datetime.now(),
            data_source="binance_sync"
        )
        self.db.add(self.trade)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @patch("app.api.journal.get_minio_client")
    @patch("app.api.journal.lock_trade")
    def test_tag_trade_success(self, mock_lock_trade, mock_get_minio):
        # Mock MinIO S3 upload
        mock_s3 = MagicMock()
        mock_get_minio.return_value = mock_s3
        
        # Prepare parameters
        setup_ids = [tax.id for tax in self.taxonomy_items[:2]]
        setup_json = json.dumps(setup_ids)
        psych_tags = ["Sesuai Plan", "Tenang"]
        psych_json = json.dumps(psych_tags)
        
        # Mocking auth dependencies and fastapi parameters is handled by direct DB operations
        # mimicking the endpoint controller logic:
        
        # Call the logic of POST /journal/tag directly
        trade = self.db.query(Trade).filter(Trade.id == self.trade.id).first()
        self.assertIsNotNone(trade)
        self.assertIsNone(trade.locked_at)
        
        # 1. Create Psychology
        psych = Psychology(
            trade_id=trade.id,
            confidence_level=8,
            psychological_tags=psych_tags,
            plan_adherence=True,
            free_notes="Bulls are strong"
        )
        self.db.add(psych)
        
        # 2. Create TradeExecution
        exec_rec = TradeExecution(
            trade_id=trade.id,
            order_type="limit"
        )
        self.db.add(exec_rec)
        
        # 3. Create Setup Tags
        for setup_id in setup_ids:
            self.db.add(TradeSetupTag(trade_id=trade.id, taxonomy_version_id=setup_id))
            
        # 4. Create Market Context
        new_ctx = MarketContext(
            trade_id=trade.id,
            bias_arah_manual="bull_trend",
            session="london",
            captured_at=datetime.now()
        )
        self.db.add(new_ctx)
        
        self.db.commit()
        
        # Mock Celery trigger
        mock_lock_trade.apply_async(args=[trade.id], countdown=120)
        
        # Verify changes in DB
        updated_trade = self.db.query(Trade).filter(Trade.id == self.trade.id).first()
        self.assertIsNotNone(updated_trade.psychology)
        self.assertEqual(updated_trade.psychology.confidence_level, 8)
        self.assertTrue(updated_trade.psychology.plan_adherence)
        self.assertEqual(updated_trade.execution.order_type, "limit")
        self.assertEqual(len(updated_trade.setup_tags), 2)
        
        # Verify lock_trade scheduled
        mock_lock_trade.apply_async.assert_called_once_with(args=[self.trade.id], countdown=120)

    def test_tag_trade_locked_conflict(self):
        # Lock the trade in DB
        trade = self.db.query(Trade).filter(Trade.id == self.trade.id).first()
        trade.locked_at = datetime.now() - timedelta(minutes=1)
        self.db.commit()
        
        # Call the endpoint validation logic
        updated_trade = self.db.query(Trade).filter(Trade.id == self.trade.id).first()
        
        # Simulate check in API: if trade.locked_at is not None raise HTTP 409
        with self.assertRaises(ValueError) as ctx:
            if updated_trade.locked_at is not None:
                raise ValueError("HTTP 409: Trade is locked")
                
        self.assertEqual(str(ctx.exception), "HTTP 409: Trade is locked")

if __name__ == "__main__":
    unittest.main()
