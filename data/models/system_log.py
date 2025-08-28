# ./database/models.py
"""
SQLAlchemy models for Robinhood Crypto Trading App
ENHANCED: Strengthened unique constraints and validation for Historical table
"""

# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation, import-outside-toplevel



from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    Index,
    CheckConstraint,
)

from .base import BaseModel 

from utils.logger import get_logger

logger = get_logger(__name__)


class SystemLog(BaseModel):
    """System logging table for trading system events - ENHANCED"""

    __tablename__ = "system_log"

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    details = Column(String(1000), nullable=True)
    confidence = Column(String(10), nullable=True)  # 'HIGH', 'MEDIUM', 'LOW', 'REJECT'
    price = Column(Float, nullable=True)

    # ENHANCED: Better indexes and constraints
    __table_args__ = (
        Index("idx_log_timestamp", "timestamp"),
        Index("idx_log_symbol_event", "symbol", "event_type"),
        Index("idx_log_event_type", "event_type"),
        Index("idx_log_confidence", "confidence"),
        Index("idx_log_symbol_timestamp", "symbol", "timestamp"),
        # Data integrity constraints
        CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW', 'REJECT') OR confidence IS NULL",
            name="check_valid_confidence",
        ),
        CheckConstraint("price >= 0 OR price IS NULL", name="check_price_positive"),
        CheckConstraint("event_type != ''", name="check_event_type_not_empty"),
        CheckConstraint("symbol != ''", name="check_symbol_not_empty"),
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
        details: str = "",
        confidence: str = "",
        price: float = 0.0,
    ) -> "SystemLog":
        """Factory method to create log entries with validation"""
        # Validate inputs
        if not symbol or not event_type:
            raise ValueError("Symbol and event_type are required")

        if confidence and confidence not in ["HIGH", "MEDIUM", "LOW", "REJECT"]:
            raise ValueError(f"Invalid confidence level: {confidence}")

        if price is not None and price < 0:
            raise ValueError("Price cannot be negative")

        return cls(
            symbol=symbol,
            event_type=event_type,
            details=details,
            confidence=confidence,
            price=price,
        )
