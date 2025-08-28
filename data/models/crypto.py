# ./database/models.py
"""
SQLAlchemy models for Robinhood Crypto Trading App
ENHANCED: Strengthened unique constraints and validation for Historical table
"""

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    CheckConstraint,
)

from .base import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)


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

    # Add constraints for data integrity
    __table_args__ = (
        CheckConstraint("minimum_order >= 0", name="check_minimum_order_positive"),
        CheckConstraint("maximum_order >= 0", name="check_maximum_order_positive"),
        CheckConstraint("bid >= 0", name="check_bid_positive"),
        CheckConstraint("ask >= 0", name="check_ask_positive"),
        CheckConstraint("mid >= 0", name="check_mid_positive"),
        CheckConstraint(
            "minimum_order <= maximum_order OR maximum_order IS NULL",
            name="check_order_size_logic",
        ),
    )

    def __repr__(self):
        return f"<Crypto(symbol='{self.symbol}', mid={self.mid}, monitored={self.monitored})>"
