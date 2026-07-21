from binance.client import Client
from sqlalchemy.orm import Session
from app.models.models import APICredential
from app.services.crypto import cipher
from app.config import settings

class BinanceService:
    @staticmethod
    def get_client(db: Session) -> Client:
        # Fetch encrypted credentials from database
        cred = db.query(APICredential).filter(APICredential.service_name == "binance").first()
        if not cred:
            raise ValueError("Kredensial API Binance belum dikonfigurasi.")
            
        try:
            api_key = cipher.decrypt(cred.encrypted_api_key)
            api_secret = cipher.decrypt(cred.encrypted_api_secret)
        except Exception as e:
            raise ValueError(f"Gagal mendeskripsi kunci API Binance: {str(e)}")
            
        # Initialize python-binance client (configured for Testnet if enabled)
        client = Client(api_key, api_secret, testnet=settings.BINANCE_USE_TESTNET)
        return client

    @classmethod
    def get_position_risk(cls, db: Session):
        client = cls.get_client(db)
        # GET /fapi/v2/positionRisk
        return client.futures_position_information()

    @classmethod
    def get_user_trades(cls, db: Session, symbol: str, start_time: int = None):
        client = cls.get_client(db)
        # GET /fapi/v1/userTrades
        if start_time:
            return client.futures_account_trades(symbol=symbol, startTime=start_time)
        return client.futures_account_trades(symbol=symbol)

    @classmethod
    def get_open_orders(cls, db: Session, symbol: str):
        client = cls.get_client(db)
        # GET /fapi/v1/openOrders
        return client.futures_get_open_orders(symbol=symbol)
