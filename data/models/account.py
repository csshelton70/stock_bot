# ./database/models.py
"""
SQLAlchemy models for Robinhood Crypto Trading App
ENHANCED: Strengthened unique constraints and validation for Historical table
"""

from sqlalchemy import (
    Column,
    String,
    Float,
    CheckConstraint,
)

from .base import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)


class Account(BaseModel):
    """Account information"""

    __tablename__ = "account"

    account_number = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=True)
    buying_power = Column(Float, nullable=True)
    currency = Column(String(10), nullable=False, default="USD")

    # Add constraints
    __table_args__ = (
        CheckConstraint("buying_power >= 0", name="check_buying_power_positive"),
    )

    def __repr__(self):
        return (
            f"<Account(account_number='{self.account_number}', status='{self.status}')>"
        )
