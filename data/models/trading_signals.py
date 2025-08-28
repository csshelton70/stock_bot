# ./database/models.py
"""
SQLAlchemy models for Robinhood Crypto Trading App
ENHANCED: Strengthened unique constraints and validation for Historical table
"""

# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation, import-outside-toplevel

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Index,
    CheckConstraint,
)

from .base import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)

class TradingSignals(BaseModel):
    """Generated trading signals with full analysis - ENHANCED"""

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

    # ENHANCED: Stronger constraints and indexes
    __table_args__ = (
        Index("idx_signal_timestamp", "created_at"),
        Index("idx_signal_symbol_type", "symbol", "signal_type"),
        Index("idx_signal_confidence", "confidence"),
        Index("idx_signal_alert", "alert_id"),
        Index("idx_signal_symbol_timestamp", "symbol", "created_at"),
        # Data integrity constraints
        CheckConstraint(
            "signal_type IN ('buy', 'sell')", name="check_valid_signal_type"
        ),
        CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW')",
            name="check_valid_signal_confidence",
        ),
        CheckConstraint("price > 0", name="check_signal_price_positive"),
        CheckConstraint(
            "rsi_15min_value >= 0 AND rsi_15min_value <= 100 OR rsi_15min_value IS NULL",
            name="check_rsi_15min_range",
        ),
        CheckConstraint(
            "rsi_1hour_value >= 0 AND rsi_1hour_value <= 100 OR rsi_1hour_value IS NULL",
            name="check_rsi_1hour_range",
        ),
    )

    def __repr__(self):
        return (
            f"<TradingSignals(symbol='{self.symbol}', type='{self.signal_type}', "
            f"confidence='{self.confidence}', price={self.price})>"
        )
