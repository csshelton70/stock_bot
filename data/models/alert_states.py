# ./database/models.py
"""
SQLAlchemy models for Robinhood Crypto Trading App
ENHANCED: Strengthened unique constraints and validation for Historical table
"""

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


class AlertStates(BaseModel):
    """Alert states tracking table for trading system - ENHANCED"""

    __tablename__ = "alert_states"

    symbol = Column(String(20), nullable=False)
    alert_type = Column(String(10), nullable=False)  # 'buy' or 'sell'
    start_time = Column(DateTime, nullable=False)
    rsi_trigger_level = Column(Float, nullable=False)
    initial_rsi = Column(Float, nullable=False)
    status = Column(
        String(20), nullable=False, default="active"
    )  # 'active', 'triggered', 'expired'

    # ENHANCED: Better indexes and constraints
    __table_args__ = (
        Index("idx_alert_symbol_status", "symbol", "status"),
        Index("idx_alert_start_time", "start_time"),
        Index("idx_alert_type_status", "alert_type", "status"),
        Index("idx_alert_symbol_type_status", "symbol", "alert_type", "status"),
        # Data integrity constraints
        CheckConstraint("alert_type IN ('buy', 'sell')", name="check_valid_alert_type"),
        CheckConstraint(
            "status IN ('active', 'triggered', 'expired')", name="check_valid_status"
        ),
        CheckConstraint(
            "rsi_trigger_level >= 0 AND rsi_trigger_level <= 100",
            name="check_rsi_trigger_range",
        ),
        CheckConstraint(
            "initial_rsi >= 0 AND initial_rsi <= 100", name="check_initial_rsi_range"
        ),
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

    def validate_rsi_values(self) -> bool:
        """Validate RSI values are in valid range"""
        return 0 <= self.rsi_trigger_level <= 100 and 0 <= self.initial_rsi <= 100
