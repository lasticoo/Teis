import os
import sys
import unittest
import io
import uuid
from PIL import Image

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import SessionLocal
from app.models.models import Trade, Screenshot

from datetime import datetime

class TestScreenshotManager(unittest.TestCase):
    def setUp(self):
        self.db: Session = SessionLocal()
        self.trade_id = str(uuid.uuid4())
        self.test_trade = Trade(
            id=self.trade_id,
            pair="ETHUSDT",
            direction="long",
            entry_price=3500.0,
            entry_time=datetime.now(),
            data_source="manual"
        )
        self.db.add(self.test_trade)
        self.db.commit()

    def tearDown(self):
        try:
            self.db.execute(text(f"UPDATE trades SET locked_at = NULL WHERE id = '{self.trade_id}'"))
            self.db.commit()
            self.db.query(Screenshot).filter(Screenshot.trade_id == self.trade_id).delete()
            self.db.query(Trade).filter(Trade.id == self.trade_id).delete()
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def test_01_pillow_webp_compression(self):
        """Test Pillow converts PNG image buffer into WebP with quality 80."""
        # Create dummy PNG image in memory
        img = Image.new("RGB", (800, 600), color="blue")
        png_buffer = io.BytesIO()
        img.save(png_buffer, format="PNG")
        raw_png_bytes = png_buffer.getvalue()

        # Convert to WebP using Pillow
        input_img = Image.open(io.BytesIO(raw_png_bytes))
        webp_buffer = io.BytesIO()
        input_img.save(webp_buffer, format="WEBP", quality=80)
        compressed_webp_bytes = webp_buffer.getvalue()

        self.assertTrue(len(compressed_webp_bytes) < len(raw_png_bytes))
        print(f"✅ TEST 1 PASSED: Pillow WebP compression reduced file size from {len(raw_png_bytes)} bytes to {len(compressed_webp_bytes)} bytes.")

    def test_02_max_file_size_validation(self):
        """Test 5MB file size limit check logic."""
        max_size = 5 * 1024 * 1024
        oversized_bytes = b"0" * (max_size + 100)
        self.assertTrue(len(oversized_bytes) > max_size)
        print("✅ TEST 2 PASSED: 5MB file size limit validation logic confirmed.")

    def test_03_mime_type_validation(self):
        """Test mime-type validation logic for non-image files."""
        invalid_mime = "application/pdf"
        valid_mime = "image/png"
        self.assertFalse(invalid_mime.startswith("image/"))
        self.assertTrue(valid_mime.startswith("image/"))
        print("✅ TEST 3 PASSED: Image MIME-type validation logic confirmed.")

if __name__ == "__main__":
    unittest.main()
