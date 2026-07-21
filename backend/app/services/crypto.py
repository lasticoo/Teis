import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

import hashlib

class AESCipher:
    def __init__(self):
        key_b64 = settings.AES_ENCRYPTION_KEY
        try:
            raw_key = base64.b64decode(key_b64)
            # Use SHA-256 hash to guarantee a secure, high-entropy 32-byte key
            self.key = hashlib.sha256(raw_key).digest()
        except Exception as e:
            # Fallback/Error handling for invalid key
            raise RuntimeError(f"Failed to initialize AES key: {str(e)}")

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        aesgcm = AESGCM(self.key)
        nonce = os.urandom(12)  # GCM standard nonce length is 12 bytes
        data = plaintext.encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, data, None)
        
        # Combine nonce, ciphertext, and tag. cryptography AEAD AESGCM encrypt appends tag at the end of ciphertext
        # so ciphertext contains both ciphertext and tag.
        # We can store base64(nonce) + ":" + base64(ciphertext_with_tag)
        nonce_b64 = base64.b64encode(nonce).decode("utf-8")
        cipher_b64 = base64.b64encode(ciphertext).decode("utf-8")
        return f"{nonce_b64}:{cipher_b64}"

    def decrypt(self, encrypted_text: str) -> str:
        if not encrypted_text:
            return ""
        try:
            parts = encrypted_text.split(":")
            if len(parts) != 2:
                raise ValueError("Encrypted text must be in format nonce_b64:cipher_b64")
            nonce_b64, cipher_b64 = parts[0], parts[1]
            nonce = base64.b64decode(nonce_b64)
            ciphertext = base64.b64decode(cipher_b64)
            
            aesgcm = AESGCM(self.key)
            decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_data.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")

# Global cipher instance
cipher = AESCipher()
