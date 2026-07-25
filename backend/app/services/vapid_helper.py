import os
import base64
import logging
from cryptography.hazmat.primitives.asymmetric import ec
from app.config import settings

logger = logging.getLogger(__name__)

# Cache for runtime keys if not set in .env
_runtime_vapid_public = None
_runtime_vapid_private = None


def generate_vapid_keypair():
    """
    Generates a valid VAPID P-256 EC Keypair for Web Push.
    Returns: (public_key_b64, private_key_b64)
    """
    priv = ec.generate_private_key(ec.SECP256R1())
    priv_num = priv.private_numbers().private_value
    priv_bytes = priv_num.to_bytes(32, byteorder='big')
    priv_b64 = base64.urlsafe_b64encode(priv_bytes).decode('utf-8').rstrip('=')

    pub_numbers = priv.public_key().public_numbers()
    x = pub_numbers.x.to_bytes(32, byteorder='big')
    y = pub_numbers.y.to_bytes(32, byteorder='big')
    pub_bytes = b'\x04' + x + y
    pub_b64 = base64.urlsafe_b64encode(pub_bytes).decode('utf-8').rstrip('=')

    return pub_b64, priv_b64


def get_vapid_keys():
    """
    Returns (public_key, private_key) VAPID keys.
    Falls back to runtime generated keys if missing in .env.
    """
    global _runtime_vapid_public, _runtime_vapid_private

    pub = settings.VAPID_PUBLIC_KEY
    priv = settings.VAPID_PRIVATE_KEY

    if pub and priv:
        return pub, priv

    if not _runtime_vapid_public or not _runtime_vapid_private:
        _runtime_vapid_public, _runtime_vapid_private = generate_vapid_keypair()
        logger.info("VAPID keys not found in settings/.env. Auto-generated runtime VAPID keypair.")

    return _runtime_vapid_public, _runtime_vapid_private
