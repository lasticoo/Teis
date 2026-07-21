import os
import sys
import unittest
import base64
import pyotp
from fastapi.testclient import TestClient

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.services.crypto import cipher
from app.services.auth import (
    get_password_hash, verify_password, verify_totp, create_access_token, decode_access_token
)

class TestAuthAndCrypto(unittest.TestCase):
    
    def test_aes_encryption_decryption(self):
        original_text = "my_binance_secret_12345"
        encrypted = cipher.encrypt(original_text)
        self.assertNotEqual(original_text, encrypted)
        
        decrypted = cipher.decrypt(encrypted)
        self.assertEqual(original_text, decrypted)
        
    def test_password_hashing(self):
        password = "my_secure_password"
        pwd_hash = get_password_hash(password)
        
        self.assertTrue(verify_password(password, pwd_hash))
        self.assertFalse(verify_password("wrong_password", pwd_hash))
        
    def test_totp_verification(self):
        # Using development key: JBSWY3DPEHPK3PXP
        secret = "JBSWY3DPEHPK3PXP"
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        
        self.assertTrue(verify_totp(secret, current_code))
        self.assertFalse(verify_totp(secret, "123456"))

    def test_jwt_token_flow(self):
        data = {"sub": "test_user", "pending_2fa": False}
        token = create_access_token(data)
        
        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["sub"], "test_user")
        self.assertEqual(decoded["pending_2fa"], False)

class TestAuthAPI(unittest.TestCase):
    
    def setUp(self):
        self.client = TestClient(app)
        
    def test_api_login_wrong_credentials(self):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "wrong_user", "password": "wrong_password"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Username atau password salah.", response.json()["detail"])

    def test_api_login_correct_credentials_and_2fa(self):
        # Standard login with default user "admin" / "securepassword"
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "securepassword"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("session_token", data)
        self.assertTrue(data["require_2fa"])
        
        # Verify 2FA with wrong token
        session_token = data["session_token"]
        response_2fa = self.client.post(
            "/api/v1/auth/verify-2fa",
            json={"totp_code": "000000"},
            headers={"Authorization": f"Bearer {session_token}"}
        )
        self.assertEqual(response_2fa.status_code, 401)
        
        # Verify 2FA with correct token (dynamic code generation)
        totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")
        correct_code = totp.now()
        response_2fa_correct = self.client.post(
            "/api/v1/auth/verify-2fa",
            json={"totp_code": correct_code},
            headers={"Authorization": f"Bearer {session_token}"}
        )
        self.assertEqual(response_2fa_correct.status_code, 200)
        self.assertIn("access_token", response_2fa_correct.json())
        
        # Check settings access
        access_token = response_2fa_correct.json()["access_token"]
        response_settings = self.client.get(
            "/api/v1/settings/binance-key",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        self.assertEqual(response_settings.status_code, 200)
        self.assertFalse(response_settings.json()["has_key"])

if __name__ == "__main__":
    unittest.main()
