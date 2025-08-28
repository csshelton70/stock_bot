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
    Boolean,
    Index,
    CheckConstraint,
)

from .base import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)


class SignalPerformance(BaseModel):
    """Track performance of generated signals - ENHANCED"""

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

    # Additional fields for enhanced tracking
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String(50), nullable=True)
    realized_pnl = Column(Float, nullable=True)
    max_profit = Column(Float, nullable=True)
    max_loss = Column(Float, nullable=True)
    hold_duration_hours = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)

    # ENHANCED: Better indexes and constraints
    __table_args__ = (
        Index("idx_perf_signal_id", "signal_id"),
        Index("idx_perf_symbol_outcome", "symbol", "outcome"),
        Index("idx_perf_confidence_outcome", "confidence", "outcome"),
        Index("idx_perf_active", "is_active"),
        Index("idx_perf_entry_time", "entry_time"),
        # Data integrity constraints
        CheckConstraint(
            "signal_type IN ('buy', 'sell')", name="check_perf_signal_type"
        ),
        CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW')", name="check_perf_confidence"
        ),
        CheckConstraint("entry_price > 0", name="check_entry_price_positive"),
        CheckConstraint(
            "current_price > 0 OR current_price IS NULL",
            name="check_current_price_positive",
        ),
        CheckConstraint(
            "exit_price > 0 OR exit_price IS NULL", name="check_exit_price_positive"
        ),
        CheckConstraint(
            "hours_since_signal >= 0 OR hours_since_signal IS NULL",
            name="check_hours_positive",
        ),
        CheckConstraint(
            "outcome IN ('profitable', 'loss', 'breakeven', 'pending') OR outcome IS NULL",
            name="check_valid_outcome",
        ),
    )

    def __repr__(self):
        return (
            f"<SignalPerformance(signal_id={self.signal_id}, symbol='{self.symbol}', "
            f"pnl={self.unrealized_pnl}, outcome='{self.outcome}')>"
        )
