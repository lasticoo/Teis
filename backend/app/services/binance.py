from decimal import Decimal
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
        
        # Synchronize local time with Binance server time to prevent clock drift issues (APIError code -1021)
        import time
        try:
            server_time = client.get_server_time()
            client.timestamp_offset = server_time['serverTime'] - int(time.time() * 1000)
        except Exception:
            pass
            
        return client

    @classmethod
    def get_position_risk(cls, db: Session):
        client = cls.get_client(db)
        
        # Fetch position risk (contains markPrice, unRealizedProfit, etc.)
        try:
            position_risk = client.futures_position_information()
        except Exception as e:
            position_risk = []
            
        # Fetch account positions (contains leverage)
        try:
            acc = client.futures_account()
            account_positions = acc.get("positions", [])
        except Exception:
            account_positions = []
            
        # Create lookup map for leverage
        leverage_map = {p["symbol"]: p.get("leverage") for p in account_positions}
        
        # Merge leverage into position risk items
        for pos in position_risk:
            symbol = pos["symbol"]
            pos["leverage"] = leverage_map.get(symbol)
            
        return position_risk

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
        
        # Fetch standard open orders
        try:
            basic_orders = client.futures_get_open_orders(symbol=symbol)
        except Exception:
            basic_orders = []
            
        # Fetch conditional algo open orders
        try:
            algo_orders = client.futures_get_open_algo_orders()
            # Filter algo orders for this symbol
            algo_orders = [o for o in algo_orders if o.get("symbol") == symbol]
        except Exception:
            algo_orders = []
            
        return {"basic": basic_orders, "algo": algo_orders}

    @classmethod
    def get_account_balance(cls, db: Session):
        client = cls.get_client(db)
        # GET /fapi/v2/balance
        balances = client.futures_account_balance()
        usdt_bal = next((b for b in balances if b.get("asset") == "USDT"), None)
        if not usdt_bal and balances:
            usdt_bal = balances[0]
        return usdt_bal

    @classmethod
    def get_all_wallets_balance(cls, db: Session):
        """
        Fetches total account balance across Futures, Funding, and Spot wallets.
        This ensures users keeping funds in Funding Wallet (e.g. $90) + Futures Wallet ($5)
        have their TRUE total account equity captured accurately.
        """
        client = cls.get_client(db)

        fut_balance = Decimal("0")
        fut_unpnl = Decimal("0")
        try:
            fut_balances = client.futures_account_balance()
            usdt_fut = next((b for b in fut_balances if b.get("asset") == "USDT"), {})
            fut_balance = Decimal(str(usdt_fut.get("balance", "0")))
            fut_unpnl = Decimal(str(usdt_fut.get("crossUnPnl", "0")))
        except Exception as e:
            logger.warning(f"Failed to fetch futures balance: {e}")

        funding_equity = Decimal("0")
        try:
            funding_assets = client._request_margin_api("post", "asset/get-funding-asset", signed=True, data={})
            usdt_funding = next((a for a in funding_assets if a.get("asset") == "USDT"), {})
            funding_free = Decimal(str(usdt_funding.get("free", "0")))
            funding_freeze = Decimal(str(usdt_funding.get("freeze", "0")))
            funding_equity = funding_free + funding_freeze
        except Exception as e:
            logger.warning(f"Failed to fetch funding assets: {e}")

        spot_equity = Decimal("0")
        try:
            spot_info = client.get_account()
            usdt_spot = next((b for b in spot_info.get("balances", []) if b.get("asset") == "USDT"), {})
            spot_free = Decimal(str(usdt_spot.get("free", "0")))
            spot_locked = Decimal(str(usdt_spot.get("locked", "0")))
            spot_equity = spot_free + spot_locked
        except Exception as e:
            logger.warning(f"Failed to fetch spot account: {e}")

        total_balance = fut_balance + funding_equity + spot_equity

        return {
            "total_balance": total_balance,
            "futures_balance": fut_balance,
            "funding_balance": funding_equity,
            "spot_balance": spot_equity,
            "crossUnPnl": fut_unpnl
        }

    @classmethod
    def get_income_history(cls, db: Session, income_type: str = "TRANSFER", start_time: int = None):
        client = cls.get_client(db)
        # GET /fapi/v1/income
        kwargs = {"incomeType": income_type}
        if start_time:
            kwargs["startTime"] = start_time
        return client.futures_income_history(**kwargs)
