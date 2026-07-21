# Import all models here so that Alembic can detect them
from app.database import Base
from app.models.models import (
    Trade,
    ExchangeFill,
    TradeFill,
    TradeExecution,
    MarketContext,
    SetupTaxonomyVersion,
    TradeSetupTag,
    Psychology,
    Screenshot,
    TradeCorrection,
    EdgeBlueprint,
    User,
    APICredential
)
