import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Enum,
    Numeric,
    DateTime,
    Integer,
    ForeignKey,
    Boolean,
    JSON,
    Text,
    UniqueConstraint,
    CheckConstraint,
    FetchedValue,
    func
)
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Trade(Base):
    __tablename__ = 'trades'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pair = Column(String(20), nullable=False)
    direction = Column(Enum('long', 'short'), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    exit_price = Column(Numeric(20, 8), nullable=True)
    stop_loss = Column(Numeric(20, 8), nullable=True)
    take_profit = Column(Numeric(20, 8), nullable=True)
    margin = Column(Numeric(20, 8), nullable=True)
    leverage = Column(Numeric(6, 2), nullable=True)
    risk_amount = Column(Numeric(20, 8), nullable=True)
    rr_planned = Column(Numeric(6, 2), nullable=True)
    rr_realized = Column(Numeric(6, 2), nullable=True)
    pnl = Column(Numeric(20, 8), nullable=True)
    fee = Column(Numeric(20, 8), nullable=True)
    entry_time = Column(DateTime(timezone=False), nullable=False)
    exit_time = Column(DateTime(timezone=False), nullable=True)
    
    # Generated column representation in SQLAlchemy
    holding_time_sec = Column(Integer, FetchedValue())
    
    data_source = Column(Enum('manual', 'binance_sync'), nullable=False)
    locked_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())

    # Relationships
    fills = relationship("TradeFill", back_populates="trade", cascade="all, delete-orphan")
    execution = relationship("TradeExecution", uselist=False, back_populates="trade", cascade="all, delete-orphan")
    market_context = relationship("MarketContext", back_populates="trade", cascade="all, delete-orphan")
    psychology = relationship("Psychology", uselist=False, back_populates="trade", cascade="all, delete-orphan")
    screenshots = relationship("Screenshot", back_populates="trade", cascade="all, delete-orphan")
    corrections = relationship("TradeCorrection", back_populates="trade", cascade="all, delete-orphan")
    setup_tags = relationship("TradeSetupTag", back_populates="trade", cascade="all, delete-orphan")


class ExchangeFill(Base):
    __tablename__ = 'exchange_fills'
    __table_args__ = (
        UniqueConstraint('symbol', 'binance_trade_id', name='uq_fill'),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    symbol = Column(String(20), nullable=False)
    binance_trade_id = Column(Integer, nullable=False)  # BigInt actually
    binance_order_id = Column(Integer, nullable=False)  # BigInt actually
    price = Column(Numeric(20, 8), nullable=False)
    qty = Column(Numeric(20, 8), nullable=False)
    fee = Column(Numeric(20, 8), nullable=False)
    funding_fee = Column(Numeric(20, 8), nullable=True)
    side = Column(String(10), nullable=False)
    executed_at = Column(DateTime(timezone=False), nullable=False)
    raw_payload = Column(JSON, nullable=True)

    # Relationships
    trade_fills = relationship("TradeFill", back_populates="exchange_fill")


class TradeFill(Base):
    __tablename__ = 'trade_fills'
    __table_args__ = (
        UniqueConstraint('trade_id', 'exchange_fill_id', name='uq_trade_fill'),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trade_id = Column(String(36), ForeignKey('trades.id'), nullable=False)
    exchange_fill_id = Column(String(36), ForeignKey('exchange_fills.id'), nullable=False)
    role = Column(Enum('entry', 'exit'), nullable=False)

    # Relationships
    trade = relationship("Trade", back_populates="fills")
    exchange_fill = relationship("ExchangeFill", back_populates="trade_fills")


class TradeExecution(Base):
    __tablename__ = 'trade_execution'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trade_id = Column(String(36), ForeignKey('trades.id'), unique=True, nullable=False)
    order_type = Column(Enum('limit', 'market'), nullable=False)
    moved_to_breakeven = Column(Boolean, nullable=False, default=False)
    trailing_stop_used = Column(Boolean, nullable=False, default=False)
    exit_reason = Column(Enum('take_profit', 'stop_loss', 'manual_close', 'breakeven'), nullable=True)

    # Relationships
    trade = relationship("Trade", back_populates="execution")


class MarketContext(Base):
    __tablename__ = 'market_context'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trade_id = Column(String(36), ForeignKey('trades.id'), nullable=False)
    trend_htf = Column(String(20), nullable=True)
    trend_ltf = Column(String(20), nullable=True)
    bias_arah_manual = Column(Enum('bull_trend', 'bear_trend', 'range'), nullable=True)
    atr = Column(Numeric(20, 8), nullable=True)
    volume_24h = Column(Numeric(24, 4), nullable=True)
    session = Column(Enum('asia', 'london', 'new_york'), nullable=False)
    btc_dominance = Column(Numeric(6, 2), nullable=True)
    fear_greed_index = Column(Integer, nullable=True)  # TinyInt Unsigned
    funding_rate = Column(Numeric(10, 6), nullable=True)
    open_interest = Column(Numeric(24, 4), nullable=True)
    captured_at = Column(DateTime(timezone=False), nullable=False)

    # Relationships
    trade = relationship("Trade", back_populates="market_context")


class SetupTaxonomyVersion(Base):
    __tablename__ = 'setup_taxonomy_versions'
    __table_args__ = (
        UniqueConstraint('version_number', 'tag_name', name='uq_version_tag'),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    version_number = Column(Integer, nullable=False)
    tag_name = Column(String(50), nullable=False)
    tag_definition = Column(Text, nullable=False)
    effective_from = Column(DateTime(timezone=False), nullable=False)
    effective_until = Column(DateTime(timezone=False), nullable=True)

    # Relationships
    trade_tags = relationship("TradeSetupTag", back_populates="taxonomy_version")


class TradeSetupTag(Base):
    __tablename__ = 'trade_setup_tags'

    trade_id = Column(String(36), ForeignKey('trades.id'), primary_key=True)
    taxonomy_version_id = Column(String(36), ForeignKey('setup_taxonomy_versions.id'), primary_key=True)

    # Relationships
    trade = relationship("Trade", back_populates="setup_tags")
    taxonomy_version = relationship("SetupTaxonomyVersion", back_populates="trade_tags")


class Psychology(Base):
    __tablename__ = 'psychology'
    __table_args__ = (
        CheckConstraint('confidence_level BETWEEN 1 AND 10', name='chk_confidence'),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trade_id = Column(String(36), ForeignKey('trades.id'), unique=True, nullable=False)
    confidence_level = Column(Integer, nullable=False)  # TinyInt Check constraint
    psychological_tags = Column(JSON, nullable=False)  # list of strings
    plan_adherence = Column(Boolean, nullable=False)
    free_notes = Column(Text, nullable=True)

    # Relationships
    trade = relationship("Trade", back_populates="psychology")


class Screenshot(Base):
    __tablename__ = 'screenshots'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trade_id = Column(String(36), ForeignKey('trades.id'), nullable=False)
    stage = Column(Enum('before_entry', 'during_trade', 'exit'), nullable=False)
    file_path = Column(String(500), nullable=False)
    uploaded_at = Column(DateTime(timezone=False), nullable=False)

    # Relationships
    trade = relationship("Trade", back_populates="screenshots")


class TradeCorrection(Base):
    __tablename__ = 'trade_corrections'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    original_trade_id = Column(String(36), ForeignKey('trades.id'), nullable=False)
    field_name = Column(String(50), nullable=False)
    old_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=True)
    reason = Column(Text, nullable=False)
    corrected_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())

    # Relationships
    trade = relationship("Trade", back_populates="corrections")


class EdgeBlueprint(Base):
    __tablename__ = 'edge_blueprints'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    setup_combination = Column(JSON, nullable=False)
    sample_size = Column(Integer, nullable=False)
    expectancy_r = Column(Numeric(8, 4), nullable=False)
    ci_lower = Column(Numeric(8, 4), nullable=False)
    ci_upper = Column(Numeric(8, 4), nullable=False)
    status = Column(Enum('learning', 'research', 'validation', 'production', 'monitoring'), nullable=False, default='learning')
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now())
