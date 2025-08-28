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
    DateTime,
    UniqueConstraint,
    Index,
    CheckConstraint,
)

from .base import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)



class Historical(BaseModel):
    """
    Historical price data with ENHANCED duplicate prevention
    FIXED: Strengthened unique constraint and validation
    """

    __tablename__ = "historical"

    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    interval_minutes = Column(Integer, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True, default=0.0)

    # ENHANCED: Strengthened constraints and indexes for better data integrity
    __table_args__ = (
        # PRIMARY CONSTRAINT: Prevent duplicates with explicit naming
        UniqueConstraint(
            "symbol",
            "timestamp",
            "interval_minutes",
            name="uix_historical_symbol_timestamp_interval",
        ),
        # Performance indexes
        Index("idx_historical_symbol_timestamp", "symbol", "timestamp"),
        Index("idx_historical_symbol_interval", "symbol", "interval_minutes"),
        Index("idx_historical_timestamp_interval", "timestamp", "interval_minutes"),
        # Data integrity constraints
        CheckConstraint("open > 0", name="check_open_positive"),
        CheckConstraint("high > 0", name="check_high_positive"),
        CheckConstraint("low > 0", name="check_low_positive"),
        CheckConstraint("close > 0", name="check_close_positive"),
        CheckConstraint("volume >= 0", name="check_volume_non_negative"),
        CheckConstraint("interval_minutes > 0", name="check_interval_positive"),
        # OHLC logic constraints
        CheckConstraint("low <= open", name="check_low_le_open"),
        CheckConstraint("low <= close", name="check_low_le_close"),
        CheckConstraint("open <= high", name="check_open_le_high"),
        CheckConstraint("close <= high", name="check_close_le_high"),
        CheckConstraint("low <= high", name="check_low_le_high"),
    )

    def __repr__(self):
        return f"<Historical(symbol='{self.symbol}', timestamp='{self.timestamp}', close={self.close})>"

    def validate_ohlc_logic(self) -> bool:
        """Validate OHLC price relationships"""
        try:
            return (
                self.low <= self.open <= self.high
                and self.low <= self.close <= self.high
                and self.low <= self.high
                and all(val > 0 for val in [self.open, self.high, self.low, self.close])
            )
        except (TypeError, AttributeError):
            return False

    @property
    def price_range(self) -> float:
        """Calculate price range (high - low)"""
        return self.high - self.low if self.high and self.low else 0.0

    @property
    def price_change(self) -> float:
        """Calculate price change (close - open)"""
        return self.close - self.open if self.close and self.open else 0.0

    @property
    def price_change_percent(self) -> float:
        """Calculate price change percentage"""
        if self.open and self.open > 0:
            return ((self.close - self.open) / self.open) * 100
        return 0.0
