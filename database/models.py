# ./database/models.py

"""
SQLAlchemy models for Robinhood Crypto Trading App
Updated to include Trading System tables for RSI + MACD analysis
"""

# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring

from datetime import datetime, timedelta
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    UniqueConstraint,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class BaseModel(Base):
    """Base model with common fields for all tables"""

    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Crypto(BaseModel):
    """Cryptocurrency pairs and current prices"""

    __tablename__ = "crypto"

    symbol = Column(String(20), unique=True, nullable=False, index=True)
    minimum_order = Column(Float, nullable=True)
    maximum_order = Column(Float, nullable=True)
    bid = Column(Float, nullable=True)
    mid = Column(Float, nullable=True)  # Calculated as (bid + ask) / 2
    ask = Column(Float, nullable=True)
    monitored = Column(
        Boolean, nullable=False, default=False
    )  # Track if this pair should be monitored

    def __repr__(self):
        return f"<Crypto(symbol='{self.symbol}', mid={self.mid}, monitored={self.monitored})>"


class Account(BaseModel):
    """Account information"""

    __tablename__ = "account"

    account_number = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=True)
    buying_power = Column(Float, nullable=True)
    currency = Column(String(10), nullable=False, default="USD")

    def __repr__(self):
        return (
            f"<Account(account_number='{self.account_number}', status='{self.status}')>"
        )


class Holdings(BaseModel):
    """Portfolio holdings"""

    __tablename__ = "holdings"

    symbol = Column(String(20), nullable=False, index=True)
    total_quantity = Column(Float, nullable=False, default=0.0)
    quantity_available_for_trading = Column(Float, nullable=False, default=0.0)
    price = Column(Float, nullable=True)
    value = Column(Float, nullable=True)  # total_quantity * price

    # Add index for efficient querying
    __table_args__ = (Index("idx_holdings_symbol_updated", "symbol", "updated_at"),)

    def __repr__(self):
        return f"<Holdings(symbol='{self.symbol}', quantity={self.total_quantity}, value={self.value})>"


class Historical(BaseModel):
    """Historical price data"""

    __tablename__ = "historical"

    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    interval_minutes = Column(Integer, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True, default=0.0)

    # Composite unique constraint to prevent duplicate entries
    __table_args__ = (
        UniqueConstraint("symbol", "timestamp", name="uix_symbol_timestamp"),
        Index("idx_historical_symbol_timestamp", "symbol", "timestamp"),
    )

    def __repr__(self):
        return f"<Historical(symbol='{self.symbol}', timestamp='{self.timestamp}', close={self.close})>"


# =============================================================================
# TRADING SYSTEM TABLES
# =============================================================================


class AlertStates(BaseModel):
    """Alert states tracking table for trading system"""

    __tablename__ = "alert_states"

    symbol = Column(String(20), nullable=False)
    alert_type = Column(String(10), nullable=False)  # 'buy' or 'sell'
    start_time = Column(DateTime, nullable=False)
    rsi_trigger_level = Column(Float, nullable=False)
    initial_rsi = Column(Float, nullable=False)
    status = Column(
        String(20), nullable=False, default="active"
    )  # 'active', 'triggered', 'expired'

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_alert_symbol_status", "symbol", "status"),
        Index("idx_alert_start_time", "start_time"),
        Index("idx_alert_type_status", "alert_type", "status"),
    )

    def __repr__(self):
        return (
            f"<AlertStates(symbol='{self.symbol}', type='{self.alert_type}', "
            f"status='{self.status}', rsi={self.initial_rsi})>"
        )

    @property
    def hours_active(self) -> float:
        """Calculate hours since alert was created"""
        if self.status == "active":
            return (datetime.utcnow() - self.start_time).total_seconds() / 3600
        elif self.updated_at:
            return (self.updated_at - self.start_time).total_seconds() / 3600
        else:
            return 0.0

    def is_expired(self, timeout_hours: int = 12) -> bool:
        """Check if alert should be expired based on timeout"""
        return self.hours_active > timeout_hours


class SystemLog(BaseModel):
    """System logging table for trading system events"""

    __tablename__ = "system_log"

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    details = Column(String(1000), nullable=True)
    confidence = Column(String(10), nullable=True)  # 'HIGH', 'MEDIUM', 'LOW', 'REJECT'
    price = Column(Float, nullable=True)

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_log_timestamp", "timestamp"),
        Index("idx_log_symbol_event", "symbol", "event_type"),
        Index("idx_log_event_type", "event_type"),
        Index("idx_log_confidence", "confidence"),
    )

    def __repr__(self):
        return (
            f"<SystemLog(symbol='{self.symbol}', event='{self.event_type}', "
            f"confidence='{self.confidence}', timestamp='{self.timestamp}')>"
        )

    @classmethod
    def create_event(
        cls,
        symbol: str,
        event_type: str,
        details: str = None,
        confidence: str = None,
        price: float = None,
    ) -> "SystemLog":
        """Factory method to create log entries"""
        return cls(
            symbol=symbol,
            event_type=event_type,
            details=details,
            confidence=confidence,
            price=price,
        )


# =============================================================================
# TRADING ANALYSIS TABLES (Future Extension)
# =============================================================================


class TradingSignals(BaseModel):
    """Generated trading signals with full analysis (future extension)"""

    __tablename__ = "trading_signals"

    symbol = Column(String(20), nullable=False, index=True)
    signal_type = Column(String(10), nullable=False)  # 'buy' or 'sell'
    confidence = Column(String(10), nullable=False)  # 'HIGH', 'MEDIUM', 'LOW'
    price = Column(Float, nullable=False)

    # RSI Analysis
    rsi_15min_value = Column(Float, nullable=True)
    rsi_15min_trend = Column(String(20), nullable=True)
    rsi_1hour_value = Column(Float, nullable=True)
    rsi_1hour_trend = Column(String(20), nullable=True)

    # MACD Analysis
    macd_line = Column(Float, nullable=True)
    macd_signal_line = Column(Float, nullable=True)
    macd_histogram = Column(Float, nullable=True)
    macd_crossover = Column(String(20), nullable=True)  # 'bullish', 'bearish', 'none'

    # Volume and Context
    volume_trend = Column(
        String(20), nullable=True
    )  # 'increasing', 'decreasing', 'stable'
    reasoning = Column(String(2000), nullable=True)  # JSON string of reasoning list

    # Alert relationship
    alert_id = Column(Integer, nullable=True)  # Reference to originating alert

    # Indexes
    __table_args__ = (
        Index("idx_signal_timestamp", "created_at"),
        Index("idx_signal_symbol_type", "symbol", "signal_type"),
        Index("idx_signal_confidence", "confidence"),
        Index("idx_signal_alert", "alert_id"),
    )

    def __repr__(self):
        return (
            f"<TradingSignals(symbol='{self.symbol}', type='{self.signal_type}', "
            f"confidence='{self.confidence}', price={self.price})>"
        )


class TechnicalIndicators(BaseModel):
    """Cached technical indicator calculations (future extension)"""

    __tablename__ = "technical_indicators"

    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)  # '15min', '1hour', '4hour', '1day'
    timestamp = Column(DateTime, nullable=False, index=True)

    # RSI Indicators
    rsi_14 = Column(Float, nullable=True)
    rsi_21 = Column(Float, nullable=True)

    # MACD Indicators
    macd_line = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    macd_histogram = Column(Float, nullable=True)

    # Moving Averages
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    ema_12 = Column(Float, nullable=True)
    ema_26 = Column(Float, nullable=True)

    # Bollinger Bands
    bb_upper = Column(Float, nullable=True)
    bb_middle = Column(Float, nullable=True)
    bb_lower = Column(Float, nullable=True)

    # Volume Indicators
    volume_sma_20 = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)  # Current volume / Average volume

    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "timestamp",
            name="uix_indicator_symbol_timeframe_timestamp",
        ),
        Index("idx_indicator_symbol_timeframe", "symbol", "timeframe"),
        Index("idx_indicator_timestamp", "timestamp"),
    )

    def __repr__(self):
        return (
            f"<TechnicalIndicators(symbol='{self.symbol}', timeframe='{self.timeframe}', "
            f"timestamp='{self.timestamp}', rsi={self.rsi_14})>"
        )


# =============================================================================
# PERFORMANCE TRACKING TABLES (Future Extension)
# =============================================================================


class SignalPerformance(BaseModel):
    """Track performance of generated signals (future extension)"""

    __tablename__ = "signal_performance"

    signal_id = Column(
        Integer, nullable=False, index=True
    )  # Reference to TradingSignals
    symbol = Column(String(20), nullable=False, index=True)
    signal_type = Column(String(10), nullable=False)
    confidence = Column(String(10), nullable=False)

    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)

    # Performance tracking (updated as time progresses)
    current_price = Column(Float, nullable=True)
    max_favorable_price = Column(Float, nullable=True)  # Best price in signal direction
    max_adverse_price = Column(Float, nullable=True)  # Worst price against signal

    # Performance metrics
    unrealized_pnl = Column(Float, nullable=True)  # Current P&L
    max_favorable_pnl = Column(Float, nullable=True)  # Best P&L achieved
    max_adverse_pnl = Column(Float, nullable=True)  # Worst drawdown

    # Time-based metrics
    hours_since_signal = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Performance evaluation
    performance_score = Column(Float, nullable=True)  # Calculated performance score
    outcome = Column(
        String(20), nullable=True
    )  # 'profitable', 'loss', 'breakeven', 'pending'

    __table_args__ = (
        Index("idx_perf_signal_id", "signal_id"),
        Index("idx_perf_symbol_outcome", "symbol", "outcome"),
        Index("idx_perf_confidence_outcome", "confidence", "outcome"),
        Index("idx_perf_active", "is_active"),
    )

    def __repr__(self):
        return (
            f"<SignalPerformance(signal_id={self.signal_id}, symbol='{self.symbol}', "
            f"pnl={self.unrealized_pnl}, outcome='{self.outcome}')>"
        )


# =============================================================================
# MODEL RELATIONSHIPS AND HELPER FUNCTIONS
# =============================================================================


def get_monitored_crypto_symbols(session) -> list:
    """Get list of symbols marked as monitored"""
    return [
        crypto.symbol
        for crypto in session.query(Crypto).filter(Crypto.monitored == True).all()
    ]


def get_active_alerts_for_symbol(session, symbol: str) -> list:
    """Get active alerts for a specific symbol"""
    return (
        session.query(AlertStates)
        .filter(AlertStates.symbol == symbol, AlertStates.status == "active")
        .all()
    )


def get_recent_system_events(session, hours: int = 24, limit: int = 100) -> list:
    """Get recent system log events"""
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    return (
        session.query(SystemLog)
        .filter(SystemLog.timestamp >= cutoff_time)
        .order_by(SystemLog.timestamp.desc())
        .limit(limit)
        .all()
    )


def cleanup_expired_alerts(session, timeout_hours: int = 12) -> int:
    """Mark expired alerts and return count"""
    cutoff_time = datetime.utcnow() - timedelta(hours=timeout_hours)
    expired_alerts = (
        session.query(AlertStates)
        .filter(AlertStates.status == "active", AlertStates.start_time < cutoff_time)
        .all()
    )

    count = 0
    for alert in expired_alerts:
        alert.status = "expired"
        count += 1

    if count > 0:
        session.commit()

    return count
