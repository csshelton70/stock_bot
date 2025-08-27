# ./database/models.py
"""
SQLAlchemy models for Robinhood Crypto Trading App
ENHANCED: Strengthened unique constraints and validation for Historical table
"""

from typing import Dict, Any, List

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
    CheckConstraint,
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


# =============================================================================
# TRADING SYSTEM TABLES - ENHANCED
# =============================================================================


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
        details: str = None,
        confidence: str = None,
        price: float = None,
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


# =============================================================================
# TRADING ANALYSIS TABLES - ENHANCED
# =============================================================================


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


# =============================================================================
# PERFORMANCE TRACKING TABLES - ENHANCED
# =============================================================================


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


# =============================================================================
# MODEL RELATIONSHIPS AND HELPER FUNCTIONS - ENHANCED
# =============================================================================


def get_monitored_crypto_symbols(session) -> list:
    """Get list of symbols marked as monitored"""
    try:
        return [
            crypto.symbol
            for crypto in session.query(Crypto).filter(Crypto.monitored == True).all()
        ]
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Error getting monitored symbols: {e}")
        return []


def get_active_alerts_for_symbol(session, symbol: str) -> list:
    """Get active alerts for a specific symbol"""
    try:
        return (
            session.query(AlertStates)
            .filter(AlertStates.symbol == symbol, AlertStates.status == "active")
            .all()
        )
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Error getting alerts for {symbol}: {e}")
        return []


def get_recent_system_events(session, hours: int = 24, limit: int = 100) -> list:
    """Get recent system log events"""
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return (
            session.query(SystemLog)
            .filter(SystemLog.timestamp >= cutoff_time)
            .order_by(SystemLog.timestamp.desc())
            .limit(limit)
            .all()
        )
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Error getting recent events: {e}")
        return []


def cleanup_expired_alerts(session, timeout_hours: int = 12) -> int:
    """Mark expired alerts and return count"""
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=timeout_hours)
        expired_alerts = (
            session.query(AlertStates)
            .filter(
                AlertStates.status == "active", AlertStates.start_time < cutoff_time
            )
            .all()
        )

        count = 0
        for alert in expired_alerts:
            alert.status = "expired"
            alert.updated_at = datetime.utcnow()
            count += 1

        if count > 0:
            session.commit()

        return count
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Error cleaning up expired alerts: {e}")
        return 0


def validate_historical_data_integrity(session) -> Dict[str, Any]:
    """
    Validate historical data integrity across all records
    NEW FUNCTION: Comprehensive validation of historical data
    """
    try:
        validation_results = {
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "duplicate_sets": 0,
            "validation_errors": [],
            "symbols_analyzed": 0,
        }

        # Get total count
        validation_results["total_records"] = session.query(Historical).count()

        # Check for duplicates using the unique constraint
        from sqlalchemy import text

        duplicate_query = text(
            """
            SELECT COUNT(*) as duplicate_count
            FROM (
                SELECT symbol, timestamp, interval_minutes, COUNT(*) as cnt
                FROM historical 
                GROUP BY symbol, timestamp, interval_minutes
                HAVING COUNT(*) > 1
            ) duplicates
        """
        )

        duplicate_result = session.execute(duplicate_query).fetchone()
        validation_results["duplicate_sets"] = (
            duplicate_result.duplicate_count if duplicate_result else 0
        )

        # Sample validation of OHLC logic
        sample_size = min(1000, validation_results["total_records"])
        if sample_size > 0:
            sample_records = (
                session.query(Historical)
                .order_by(Historical.id.desc())
                .limit(sample_size)
                .all()
            )

            valid_count = 0
            for record in sample_records:
                if record.validate_ohlc_logic():
                    valid_count += 1
                else:
                    validation_results["validation_errors"].append(
                        f"Invalid OHLC logic: {record.symbol} at {record.timestamp}"
                    )

            validation_results["valid_records"] = valid_count
            validation_results["invalid_records"] = sample_size - valid_count

        # Count unique symbols
        validation_results["symbols_analyzed"] = (
            session.query(Historical.symbol).distinct().count()
        )

        return validation_results

    except Exception as e:
        import logging

        logging.getLogger(__name__).error(
            f"Error validating historical data integrity: {e}"
        )
        return {
            "error": str(e),
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "duplicate_sets": 0,
            "validation_errors": [f"Validation failed: {e}"],
            "symbols_analyzed": 0,
        }


def get_data_coverage_report(session) -> Dict[str, Any]:
    """
    Generate data coverage report
    NEW FUNCTION: Analyzes data completeness across symbols and timeframes
    """
    try:
        from sqlalchemy import text

        coverage_query = text(
            """
            SELECT 
                h.symbol,
                h.interval_minutes,
                COUNT(*) as record_count,
                MIN(h.timestamp) as earliest_data,
                MAX(h.timestamp) as latest_data,
                c.monitored
            FROM historical h
            LEFT JOIN crypto c ON h.symbol = c.symbol
            GROUP BY h.symbol, h.interval_minutes
            ORDER BY c.monitored DESC, h.symbol, h.interval_minutes
        """
        )

        results = session.execute(coverage_query).fetchall()

        coverage_report = {
            "symbols_with_data": 0,
            "total_symbols_monitored": 0,
            "coverage_by_symbol": {},
            "coverage_summary": {
                "15min": {"symbols": 0, "total_records": 0},
                "60min": {"symbols": 0, "total_records": 0},
                "other": {"symbols": 0, "total_records": 0},
            },
        }

        symbols_seen = set()
        for row in results:
            symbol = row.symbol
            interval = row.interval_minutes

            symbols_seen.add(symbol)

            if row.monitored:
                coverage_report["total_symbols_monitored"] += 1

            # Categorize by interval
            if interval == 15:
                coverage_report["coverage_summary"]["15min"]["symbols"] += 1
                coverage_report["coverage_summary"]["15min"][
                    "total_records"
                ] += row.record_count
            elif interval == 60:
                coverage_report["coverage_summary"]["60min"]["symbols"] += 1
                coverage_report["coverage_summary"]["60min"][
                    "total_records"
                ] += row.record_count
            else:
                coverage_report["coverage_summary"]["other"]["symbols"] += 1
                coverage_report["coverage_summary"]["other"][
                    "total_records"
                ] += row.record_count

            # Symbol-specific coverage
            if symbol not in coverage_report["coverage_by_symbol"]:
                coverage_report["coverage_by_symbol"][symbol] = {
                    "monitored": bool(row.monitored),
                    "intervals": {},
                }

            # Calculate data span
            if row.earliest_data and row.latest_data:
                earliest = row.earliest_data
                latest = row.latest_data
                if isinstance(earliest, str):
                    from datetime import datetime

                    earliest = datetime.fromisoformat(earliest)
                    latest = datetime.fromisoformat(latest)

                days_span = (latest - earliest).days
                hours_since_update = (datetime.utcnow() - latest).total_seconds() / 3600
            else:
                days_span = 0
                hours_since_update = None

            coverage_report["coverage_by_symbol"][symbol]["intervals"][
                f"{interval}min"
            ] = {
                "record_count": row.record_count,
                "earliest_data": row.earliest_data,
                "latest_data": row.latest_data,
                "days_span": days_span,
                "hours_since_update": hours_since_update,
                "is_recent": hours_since_update < 2 if hours_since_update else False,
            }

        coverage_report["symbols_with_data"] = len(symbols_seen)

        return coverage_report

    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Error generating coverage report: {e}")
        return {"error": str(e)}


# =============================================================================
# DATABASE MAINTENANCE FUNCTIONS
# =============================================================================


def create_missing_indexes(session) -> List[str]:
    """
    Create any missing indexes for optimal performance
    NEW FUNCTION: Ensures all performance indexes are present
    """
    try:
        from sqlalchemy import text

        created_indexes = []

        # Define critical indexes that should exist
        critical_indexes = [
            {
                "name": "idx_historical_symbol_timestamp_interval",
                "sql": "CREATE INDEX IF NOT EXISTS idx_historical_symbol_timestamp_interval ON historical(symbol, timestamp, interval_minutes)",
            },
            {
                "name": "idx_historical_timestamp_desc",
                "sql": "CREATE INDEX IF NOT EXISTS idx_historical_timestamp_desc ON historical(timestamp DESC)",
            },
            {
                "name": "idx_crypto_monitored",
                "sql": "CREATE INDEX IF NOT EXISTS idx_crypto_monitored ON crypto(monitored) WHERE monitored = 1",
            },
            {
                "name": "idx_alerts_active",
                "sql": "CREATE INDEX IF NOT EXISTS idx_alerts_active ON alert_states(status) WHERE status = 'active'",
            },
        ]

        for index_def in critical_indexes:
            try:
                session.execute(text(index_def["sql"]))
                created_indexes.append(index_def["name"])
            except Exception as e:
                import logging

                logging.getLogger(__name__).debug(
                    f"Index {index_def['name']} might already exist: {e}"
                )

        if created_indexes:
            session.commit()

        return created_indexes

    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Error creating indexes: {e}")
        return []


def verify_database_constraints(session) -> Dict[str, Any]:
    """
    Verify that all database constraints are working properly
    NEW FUNCTION: Tests constraint enforcement
    """
    try:
        verification_results = {
            "constraints_tested": 0,
            "constraints_working": 0,
            "constraint_failures": [],
            "test_results": {},
        }

        # Test Historical table unique constraint
        try:
            from sqlalchemy.exc import IntegrityError

            # Try to insert duplicate historical record
            test_time = datetime.utcnow()
            duplicate_record = Historical(
                symbol="TEST-CONSTRAINT",
                timestamp=test_time,
                interval_minutes=15,
                open=100.0,
                high=100.0,
                low=100.0,
                close=100.0,
                volume=0.0,
            )

            # Insert first record
            session.add(duplicate_record)
            session.flush()

            # Try to insert duplicate - should fail
            duplicate_record2 = Historical(
                symbol="TEST-CONSTRAINT",
                timestamp=test_time,
                interval_minutes=15,
                open=101.0,  # Different values but same key
                high=101.0,
                low=101.0,
                close=101.0,
                volume=0.0,
            )

            session.add(duplicate_record2)

            try:
                session.flush()
                # If we get here, constraint is NOT working
                verification_results["constraint_failures"].append(
                    "Historical unique constraint NOT enforced"
                )
                verification_results["test_results"]["historical_unique"] = "FAILED"
            except IntegrityError:
                # Expected behavior - constraint is working
                session.rollback()
                verification_results["constraints_working"] += 1
                verification_results["test_results"]["historical_unique"] = "PASSED"

            verification_results["constraints_tested"] += 1

            # Clean up test data
            session.query(Historical).filter(
                Historical.symbol == "TEST-CONSTRAINT"
            ).delete()
            session.commit()

        except Exception as e:
            verification_results["constraint_failures"].append(
                f"Error testing historical constraint: {e}"
            )

        # Test check constraints (basic validation)
        try:
            # Test positive price constraint
            invalid_historical = Historical(
                symbol="TEST-CONSTRAINT-2",
                timestamp=datetime.utcnow(),
                interval_minutes=15,
                open=-100.0,  # Invalid negative price
                high=100.0,
                low=100.0,
                close=100.0,
                volume=0.0,
            )

            session.add(invalid_historical)

            try:
                session.flush()
                # If successful, check constraint is not working
                verification_results["constraint_failures"].append(
                    "Historical price check constraint NOT enforced"
                )
                verification_results["test_results"][
                    "historical_price_check"
                ] = "FAILED"

                # Clean up
                session.query(Historical).filter(
                    Historical.symbol == "TEST-CONSTRAINT-2"
                ).delete()

            except IntegrityError:
                # Expected - constraint working
                session.rollback()
                verification_results["constraints_working"] += 1
                verification_results["test_results"][
                    "historical_price_check"
                ] = "PASSED"

            verification_results["constraints_tested"] += 1

        except Exception as e:
            verification_results["constraint_failures"].append(
                f"Error testing check constraint: {e}"
            )

        return verification_results

    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Error verifying database constraints: {e}")
        return {
            "error": str(e),
            "constraints_tested": 0,
            "constraints_working": 0,
            "constraint_failures": [f"Constraint verification failed: {e}"],
            "test_results": {},
        }
