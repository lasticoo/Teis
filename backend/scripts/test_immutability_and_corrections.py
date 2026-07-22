import os
import sys
import unittest
from datetime import datetime, timedelta
import uuid

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError
from app.database import SessionLocal
from app.models.models import (
    Trade, Psychology, TradeExecution, TradeCorrection
)

class TestImmutabilityAndCorrections(unittest.TestCase):
    def setUp(self):
        self.db: Session = SessionLocal()
        # Create a test trade
        self.trade_id = str(uuid.uuid4())
        self.test_trade = Trade(
            id=self.trade_id,
            pair="BTCUSDT",
            direction="long",
            entry_price=65000.0,
            entry_time=datetime.utcnow(),
            data_source="manual",
            locked_at=None  # Initially unlocked
        )
        self.db.add(self.test_trade)

        # Add initial psychology record
        self.psych_id = str(uuid.uuid4())
        self.psych = Psychology(
            id=self.psych_id,
            trade_id=self.trade_id,
            confidence_level=7,
            psychological_tags=["CALM", "CONFIDENT"],
            plan_adherence=True,
            free_notes="Initial notes before lock."
        )
        self.db.add(self.psych)

        # Add initial execution record
        self.exec_id = str(uuid.uuid4())
        self.execution = TradeExecution(
            id=self.exec_id,
            trade_id=self.trade_id,
            order_type="limit",
            moved_to_breakeven=False,
            trailing_stop_used=False
        )
        self.db.add(self.execution)

        self.db.commit()

    def tearDown(self):
        # Cleanup test records
        try:
            self.db.execute(text(f"UPDATE trades SET locked_at = NULL WHERE id = '{self.trade_id}'"))
            self.db.commit()
            self.db.query(TradeCorrection).filter(TradeCorrection.original_trade_id == self.trade_id).delete()
            self.db.query(Psychology).filter(Psychology.trade_id == self.trade_id).delete()
            self.db.query(TradeExecution).filter(TradeExecution.trade_id == self.trade_id).delete()
            self.db.query(Trade).filter(Trade.id == self.trade_id).delete()
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def test_01_unlocked_trade_can_be_updated(self):
        """Test that psychology can be updated while trade is unlocked (locked_at IS NULL)."""
        self.psych.confidence_level = 9
        self.db.commit()

        updated_psych = self.db.query(Psychology).filter(Psychology.trade_id == self.trade_id).first()
        self.assertEqual(updated_psych.confidence_level, 9)
        print("✅ TEST 1 PASSED: Unlocked trade permits direct updates.")

    def test_02_mysql_trigger_blocks_direct_update_when_locked(self):
        """Test that MySQL Trigger throws SQLSTATE 45000 when attempting UPDATE on locked psychology record."""
        # Lock the trade
        self.test_trade.locked_at = datetime.utcnow()
        self.db.commit()

        # Attempt direct UPDATE on psychology
        with self.assertRaises(OperationalError) as ctx:
            self.db.execute(
                text(f"UPDATE psychology SET confidence_level = 1 WHERE trade_id = '{self.trade_id}'")
            )
            self.db.commit()

        self.db.rollback()
        err_msg = str(ctx.exception)
        self.assertTrue("Trade sudah terkunci" in err_msg or "45000" in err_msg)
        print("✅ TEST 2 PASSED: MySQL Trigger successfully blocks direct UPDATE on locked trade with SQLSTATE 45000.")

    def test_03_trade_corrections_audit_log(self):
        """Test that trade_corrections audit log correctly records valid corrections on locked trade."""
        # Lock the trade
        self.test_trade.locked_at = datetime.utcnow()
        self.db.commit()

        # Add correction audit record
        corr = TradeCorrection(
            original_trade_id=self.trade_id,
            field_name="confidence_level",
            old_value="7",
            new_value="9",
            reason="Evaluasi ulang setup pasca-trade menunjukkan konfirmasi HTF yang valid.",
            corrected_at=datetime.utcnow()
        )
        self.db.add(corr)
        self.db.commit()

        saved_corr = self.db.query(TradeCorrection).filter(TradeCorrection.original_trade_id == self.trade_id).first()
        self.assertIsNotNone(saved_corr)
        self.assertEqual(saved_corr.field_name, "confidence_level")
        self.assertEqual(saved_corr.old_value, "7")
        self.assertEqual(saved_corr.new_value, "9")
        self.assertTrue(len(saved_corr.reason) >= 10)
        print("✅ TEST 3 PASSED: TradeCorrection audit log successfully records correction on locked trade.")

if __name__ == "__main__":
    unittest.main()
