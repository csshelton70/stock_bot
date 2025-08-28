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
    Index,
    CheckConstraint,
)

from .base import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)




class Holdings(BaseModel):
    """Portfolio holdings"""

    __tablename__ = "holdings"

    symbol = Column(String(20), nullable=False, index=True)
    total_quantity = Column(Float, nullable=False, default=0.0)
    quantity_available_for_trading = Column(Float, nullable=False, default=0.0)
    price = Column(Float, nullable=True)
    value = Column(Float, nullable=True)  # total_quantity * price

    # Add constraints for data integrity
    __table_args__ = (
        Index("idx_holdings_symbol_updated", "symbol", "updated_at"),
        CheckConstraint("total_quantity >= 0", name="check_total_quantity_positive"),
        CheckConstraint(
            "quantity_available_for_trading >= 0",
            name="check_available_quantity_positive",
        ),
        CheckConstraint(
            "quantity_available_for_trading <= total_quantity",
            name="check_available_le_total",
        ),
        CheckConstraint("price >= 0 OR price IS NULL", name="check_price_positive"),
        CheckConstraint("value >= 0 OR value IS NULL", name="check_value_positive"),
    )

    def __repr__(self):
        return f"<Holdings(symbol='{self.symbol}', quantity={self.total_quantity}, value={self.value})>"
