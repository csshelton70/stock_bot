# ./database/models.py
"""
SQLAlchemy models for Robinhood Crypto Trading App
ENHANCED: Strengthened unique constraints and validation for Historical table
"""

# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation, import-outside-toplevel

from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    UniqueConstraint,
    Index,
    CheckConstraint,
)

from .base import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)

class TechnicalIndicators(BaseModel):
    """Cached technical indicator calculations - ENHANCED"""

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

    # ENHANCED: Stronger constraints and indexes
    __table_args__ = (
        # CRITICAL: Unique constraint to prevent duplicate indicator calculations
        UniqueConstraint(
            "symbol",
            "timeframe",
            "timestamp",
            name="uix_indicator_symbol_timeframe_timestamp",
        ),
        Index("idx_indicator_symbol_timeframe", "symbol", "timeframe"),
        Index("idx_indicator_timestamp", "timestamp"),
        Index("idx_indicator_symbol_timestamp", "symbol", "timestamp"),
        # Data integrity constraints for RSI
        CheckConstraint(
            "rsi_14 >= 0 AND rsi_14 <= 100 OR rsi_14 IS NULL", name="check_rsi_14_range"
        ),
        CheckConstraint(
            "rsi_21 >= 0 AND rsi_21 <= 100 OR rsi_21 IS NULL", name="check_rsi_21_range"
        ),
        # Valid timeframe constraint
        CheckConstraint(
            "timeframe IN ('15min', '1hour', '4hour', '1day')",
            name="check_valid_timeframe",
        ),
        # Bollinger Bands logic
        CheckConstraint(
            "bb_lower <= bb_middle OR bb_lower IS NULL OR bb_middle IS NULL",
            name="check_bb_lower_le_middle",
        ),
        CheckConstraint(
            "bb_middle <= bb_upper OR bb_middle IS NULL OR bb_upper IS NULL",
            name="check_bb_middle_le_upper",
        ),
    )

    def __repr__(self):
        return (
            f"<TechnicalIndicators(symbol='{self.symbol}', timeframe='{self.timeframe}', "
            f"timestamp='{self.timestamp}', rsi={self.rsi_14})>"
        )
