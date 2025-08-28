#!/usr/bin/env python3
"""
Improved Database Operations for Robinhood Crypto Trading App
Enhanced with Trading System operations and better error handling
"""
# pylint:disable=broad-exception-caught,logging-fstring-interpolation

from utils.logger import get_logger
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, func


from data import (
    Crypto,
    Account,
    Holdings,
    Historical,
    AlertStates,
    SystemLog,
    TradingSignals,
    TechnicalIndicators,
    SignalPerformance,
)

logger = get_logger("database_operations")


class DatabaseOperations:
    """Enhanced database operations with improved error handling"""

    # =============================================================================
    # CORE CRYPTO DATA OPERATIONS
    # =============================================================================

    @staticmethod
    def upsert_crypto_data(session: Session, crypto_data: List[Dict[str, Any]]) -> int:
        """Insert or update crypto price data with better error handling"""
        if not crypto_data:
            return 0

        count = 0
        errors = []

        for data in crypto_data:
            try:
                symbol = data.get("symbol")
                if not symbol:
                    continue

                existing = session.query(Crypto).filter_by(symbol=symbol).first()

                if existing:
                    # Update existing record
                    for key, value in data.items():
                        if key != "symbol" and hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    # Create new record
                    crypto = Crypto(**data)
                    session.add(crypto)

                count += 1

            except Exception as e:
                error_msg = f"Error processing crypto data for {data.get('symbol', 'unknown')}: {e}"
                errors.append(error_msg)
                logger.warning(error_msg)
                continue

        if errors and len(errors) > 5:
            logger.error(f"Multiple crypto data errors ({len(errors)} total)")

        session.flush()
        logger.info(f"Processed {count} crypto records")
        return count

    @staticmethod
    def upsert_account_data(session: Session, account_data: Dict[str, Any]) -> bool:
        """Insert or update account data"""
        try:
            account_number = account_data.get("account_number")
            if not account_number:
                logger.error("Account number is required")
                return False

            existing = (
                session.query(Account).filter_by(account_number=account_number).first()
            )

            if existing:
                for key, value in account_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                account = Account(**account_data)
                session.add(account)

            session.flush()
            logger.info(f"Account data processed for {account_number}")
            return True

        except Exception as e:
            logger.error(f"Error upserting account data: {e}")
            return False

    @staticmethod
    def replace_holdings_data(
        session: Session, holdings_data: List[Dict[str, Any]]
    ) -> int:
        """Replace all holdings data efficiently"""
        try:
            # Clear existing holdings
            session.query(Holdings).delete()
            session.flush()

            if not holdings_data:
                return 0

            # Bulk insert new holdings
            count = 0
            for data in holdings_data:
                try:
                    holding = Holdings(**data)
                    session.add(holding)
                    count += 1
                except Exception as e:
                    logger.warning(
                        f"Error adding holding {data.get('symbol', 'unknown')}: {e}"
                    )
                    continue

            session.flush()
            logger.info(f"Replaced holdings with {count} records")
            return count

        except Exception as e:
            logger.error(f"Error replacing holdings data: {e}")
            return 0

    @staticmethod
    def insert_historical_data(
        session: Session, historical_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk insert historical data with duplicate handling"""
        if not historical_data:
            return 0

        try:
            # Sort data by symbol and timestamp for efficient processing
            historical_data.sort(
                key=lambda x: (x.get("symbol", ""), x.get("timestamp", datetime.min))
            )

            count = 0
            batch_size = 1000

            for i in range(0, len(historical_data), batch_size):
                batch = historical_data[i : i + batch_size]

                for data in batch:
                    try:
                        # Check for required fields
                        if not all(
                            k in data
                            for k in ["symbol", "timestamp", "interval_minutes"]
                        ):
                            continue

                        # Check for duplicates (simple approach)
                        existing = (
                            session.query(Historical)
                            .filter(
                                and_(
                                    Historical.symbol == data["symbol"],
                                    Historical.timestamp == data["timestamp"],
                                    Historical.interval_minutes
                                    == data["interval_minutes"],
                                )
                            )
                            .first()
                        )

                        if not existing:
                            historical = Historical(**data)
                            session.add(historical)
                            count += 1

                    except Exception as e:
                        logger.warning(f"Skipping historical record: {e}")
                        continue

                # Flush batch
                if count % batch_size == 0:
                    session.flush()

            session.flush()
            logger.info(f"Inserted {count} new historical records")
            return count

        except Exception as e:
            logger.error(f"Error bulk inserting historical data: {e}")
            return 0

    @staticmethod
    def get_latest_historical_timestamp(
        session: Session, symbol: str, interval_minutes: int
    ) -> Optional[datetime]:
        """Get latest timestamp for historical data"""
        try:
            result = (
                session.query(func.max(Historical.timestamp))
                .filter(
                    Historical.symbol == symbol,
                    Historical.interval_minutes == interval_minutes,
                )
                .scalar()
            )
            return result
        except Exception as e:
            logger.error(f"Error getting latest timestamp for {symbol}: {e}")
            return None

    @staticmethod
    def get_crypto_price(session: Session, symbol: str) -> Optional[float]:
        """Get current price for a crypto symbol"""
        try:
            crypto = session.query(Crypto).filter_by(symbol=symbol).first()
            if crypto and crypto.mid is not None:
                return float(crypto.mid)
            return None
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None

    @staticmethod
    def get_account_currency(session: Session) -> str:
        """Get account currency, defaults to USD"""
        try:
            account = session.query(Account).first()
            if account and account.currency:
                return str(account.currency)
            return "USD"
        except Exception as e:
            logger.error(f"Error getting account currency: {e}")
            return "USD"

    @staticmethod
    def validate_database_integrity(session: Session) -> Dict[str, Any]:
        """Validate database integrity and return status report"""
        try:
            integrity_report = {
                "timestamp": datetime.utcnow(),
                "status": "healthy",
                "issues": [],
                "warnings": [],
                "statistics": {},
            }

            # Check for orphaned records
            orphaned_historical = (
                session.query(Historical)
                .outerjoin(Crypto, Historical.symbol == Crypto.symbol)
                .filter(Crypto.symbol.is_(None))
                .count()
            )

            if orphaned_historical > 0:
                integrity_report["warnings"].append(
                    f"Found {orphaned_historical} historical records with no corresponding crypto entry"
                )

            # Check for missing prices
            symbols_without_prices = (
                session.query(Crypto)
                .filter(Crypto.monitored == True, Crypto.mid.is_(None))
                .count()
            )

            if symbols_without_prices > 0:
                integrity_report["warnings"].append(
                    f"Found {symbols_without_prices} monitored symbols without current prices"
                )

            # Check for stale data
            stale_cutoff = datetime.utcnow() - timedelta(hours=24)
            stale_data = (
                session.query(Historical)
                .filter(Historical.timestamp < stale_cutoff)
                .count()
            )

            # Collect statistics
            integrity_report["statistics"] = {
                "total_crypto_symbols": session.query(Crypto).count(),
                "monitored_symbols": session.query(Crypto)
                .filter(Crypto.monitored == True)
                .count(),
                "total_historical_records": session.query(Historical).count(),
                "total_holdings": session.query(Holdings).count(),
                "active_alerts": session.query(AlertStates)
                .filter(AlertStates.status == "active")
                .count(),
                "log_entries_24h": session.query(SystemLog)
                .filter(SystemLog.timestamp >= datetime.utcnow() - timedelta(hours=24))
                .count(),
            }

            logger.info("Database integrity check completed")
            return integrity_report

        except Exception as e:
            logger.error(f"Error validating database integrity: {e}")
            return {
                "timestamp": datetime.utcnow(),
                "status": "error",
                "error": str(e),
                "issues": ["Database integrity check failed"],
                "warnings": [],
                "statistics": {},
            }

    # =============================================================================
    # ALERT MANAGEMENT OPERATIONS
    # =============================================================================

    @staticmethod
    def get_active_alerts(session: Session, symbol: str = None) -> List[AlertStates]:
        """Get active alerts, optionally filtered by symbol"""
        query = session.query(AlertStates).filter(AlertStates.status == "active")

        if symbol:
            query = query.filter(AlertStates.symbol == symbol)

        return query.order_by(AlertStates.start_time.desc()).all()

    @staticmethod
    def create_alert(
        session: Session,
        symbol: str,
        alert_type: str,
        initial_rsi: float,
        rsi_trigger_level: float = None,
    ) -> AlertStates:
        """Create new trading alert"""
        try:
            # Check for existing active alert of same type for symbol
            existing = (
                session.query(AlertStates)
                .filter(
                    AlertStates.symbol == symbol,
                    AlertStates.alert_type == alert_type,
                    AlertStates.status == "active",
                )
                .first()
            )

            if existing:
                logger.info(f"Active {alert_type} alert already exists for {symbol}")
                return existing

            # Set default trigger level
            if rsi_trigger_level is None:
                rsi_trigger_level = 70 if alert_type == "sell" else 30

            alert = AlertStates(
                symbol=symbol,
                alert_type=alert_type,
                start_time=datetime.utcnow(),
                rsi_trigger_level=rsi_trigger_level,
                initial_rsi=initial_rsi,
                status="active",
            )

            session.add(alert)
            session.flush()  # Get the ID

            logger.info(f"Created {alert_type} alert for {symbol} (ID: {alert.id})")
            return alert

        except SQLAlchemyError as e:
            logger.error(f"Error creating alert: {e}")
            session.rollback()
            raise

    @staticmethod
    def update_alert_status(
        session: Session, alert_id: int, status: str, details: str = None
    ) -> bool:
        """Update alert status"""
        try:
            alert = (
                session.query(AlertStates).filter(AlertStates.id == alert_id).first()
            )

            if not alert:
                logger.warning(f"Alert {alert_id} not found")
                return False

            old_status = alert.status
            alert.status = status
            alert.updated_at = datetime.utcnow()

            # Log status change
            DatabaseOperations.log_system_event(
                session,
                alert.symbol,
                f"ALERT_STATUS_CHANGE",
                f"Alert {alert_id}: {old_status} -> {status}. {details or ''}",
            )

            logger.info(f"Updated alert {alert_id} status: {old_status} -> {status}")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error updating alert status: {e}")
            session.rollback()
            raise

    @staticmethod
    def expire_old_alerts(session: Session, timeout_hours: int = 12) -> int:
        """Expire alerts older than specified hours"""
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

                # Log expiration
                DatabaseOperations.log_system_event(
                    session,
                    alert.symbol,
                    "ALERT_EXPIRED",
                    f"Alert {alert.id} expired after {timeout_hours}h",
                )

            if count > 0:
                logger.info(f"Expired {count} old alerts")

            return count

        except SQLAlchemyError as e:
            logger.error(f"Error expiring alerts: {e}")
            session.rollback()
            raise

    # =============================================================================
    # TRADING SIGNALS OPERATIONS
    # =============================================================================

    @staticmethod
    def save_trading_signal(
        session: Session, signal_data: Dict[str, Any]
    ) -> TradingSignals:
        """Save trading signal with comprehensive data"""
        try:
            signal = TradingSignals(
                symbol=signal_data["symbol"],
                signal_type=signal_data["signal_type"],
                confidence=signal_data["confidence"],
                price=signal_data["price"],
                rsi_15min_value=signal_data.get("rsi_15min_value"),
                rsi_15min_trend=signal_data.get("rsi_15min_trend"),
                rsi_1hour_value=signal_data.get("rsi_1hour_value"),
                rsi_1hour_trend=signal_data.get("rsi_1hour_trend"),
                macd_line=signal_data.get("macd_line"),
                macd_signal_line=signal_data.get("macd_signal_line"),
                macd_histogram=signal_data.get("macd_histogram"),
                macd_crossover=signal_data.get("macd_crossover"),
                volume_trend=signal_data.get("volume_trend"),
                reasoning=json.dumps(signal_data.get("reasoning", [])),
                alert_id=signal_data.get("alert_id"),
            )

            session.add(signal)
            session.flush()

            # Create performance tracking record
            DatabaseOperations.create_signal_performance_record(
                session, signal.id, signal_data
            )

            logger.info(
                f"Saved {signal.confidence} {signal.signal_type} signal for {signal.symbol}"
            )
            return signal

        except SQLAlchemyError as e:
            logger.error(f"Error saving trading signal: {e}")
            session.rollback()
            raise

    @staticmethod
    def get_recent_signals(
        session: Session,
        hours: int = 24,
        confidence_levels: List[str] = None,
        symbol: str = None,
    ) -> List[TradingSignals]:
        """Get recent trading signals with optional filters"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = session.query(TradingSignals).filter(
            TradingSignals.created_at >= cutoff_time
        )

        if confidence_levels:
            query = query.filter(TradingSignals.confidence.in_(confidence_levels))

        if symbol:
            query = query.filter(TradingSignals.symbol == symbol)

        return query.order_by(TradingSignals.created_at.desc()).all()

    @staticmethod
    def get_signal_performance_summary(
        session: Session, days: int = 7
    ) -> Dict[str, Any]:
        """Get comprehensive signal performance summary"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Basic signal counts
        total_signals = (
            session.query(TradingSignals)
            .filter(TradingSignals.created_at >= cutoff_date)
            .count()
        )

        # Confidence distribution
        confidence_dist = (
            session.query(
                TradingSignals.confidence, func.count(TradingSignals.id).label("count")
            )
            .filter(TradingSignals.created_at >= cutoff_date)
            .group_by(TradingSignals.confidence)
            .all()
        )

        # Signal type distribution
        type_dist = (
            session.query(
                TradingSignals.signal_type, func.count(TradingSignals.id).label("count")
            )
            .filter(TradingSignals.created_at >= cutoff_date)
            .group_by(TradingSignals.signal_type)
            .all()
        )

        # Most active symbols
        symbol_activity = (
            session.query(
                TradingSignals.symbol,
                func.count(TradingSignals.id).label("signal_count"),
            )
            .filter(TradingSignals.created_at >= cutoff_date)
            .group_by(TradingSignals.symbol)
            .order_by(func.count(TradingSignals.id).desc())
            .limit(10)
            .all()
        )

        # Performance metrics (if available)
        perf_stats = (
            session.query(
                func.avg(SignalPerformance.pnl_percent).label("avg_pnl"),
                func.count(SignalPerformance.id).label("tracked_signals"),
                func.avg(SignalPerformance.hold_duration_hours).label("avg_hold_hours"),
            )
            .filter(SignalPerformance.created_at >= cutoff_date)
            .first()
        )

        return {
            "period_days": days,
            "total_signals": total_signals,
            "confidence_distribution": {conf: count for conf, count in confidence_dist},
            "type_distribution": {
                signal_type: count for signal_type, count in type_dist
            },
            "most_active_symbols": [
                {"symbol": symbol, "count": count} for symbol, count in symbol_activity
            ],
            "performance_stats": {
                "avg_pnl_percent": (
                    float(perf_stats.avg_pnl) if perf_stats.avg_pnl else None
                ),
                "tracked_signals": perf_stats.tracked_signals,
                "avg_hold_hours": (
                    float(perf_stats.avg_hold_hours)
                    if perf_stats.avg_hold_hours
                    else None
                ),
            },
        }

    # =============================================================================
    # SIGNAL PERFORMANCE TRACKING
    # =============================================================================

    @staticmethod
    def create_signal_performance_record(
        session: Session, signal_id: int, signal_data: Dict[str, Any]
    ) -> SignalPerformance:
        """Create performance tracking record for a signal"""
        try:
            performance = SignalPerformance(
                signal_id=signal_id,
                symbol=signal_data["symbol"],
                signal_type=signal_data["signal_type"],
                confidence=signal_data["confidence"],
                entry_price=signal_data["price"],
                current_price=signal_data["price"],
                is_active=True,
            )

            session.add(performance)
            logger.info(f"Created performance tracking for signal {signal_id}")
            return performance

        except SQLAlchemyError as e:
            logger.error(f"Error creating performance record: {e}")
            session.rollback()
            raise

    @staticmethod
    def update_signal_performance(
        session: Session,
        signal_id: int,
        current_price: float,
        exit_price: float = None,
        exit_reason: str = None,
    ) -> bool:
        """Update signal performance with current market data"""
        try:
            performance = (
                session.query(SignalPerformance)
                .filter(
                    SignalPerformance.signal_id == signal_id,
                    SignalPerformance.is_active == True,
                )
                .first()
            )

            if not performance:
                logger.warning(f"No active performance record for signal {signal_id}")
                return False

            # Update current price and unrealized P&L
            performance.current_price = current_price

            # Calculate P&L based on signal type
            if performance.signal_type == "buy":
                pnl_percent = (
                    (current_price - performance.entry_price) / performance.entry_price
                ) * 100
            else:  # sell signal
                pnl_percent = (
                    (performance.entry_price - current_price) / performance.entry_price
                ) * 100

            performance.unrealized_pnl = pnl_percent
            performance.pnl_percent = pnl_percent

            # Update max profit/loss
            performance.max_profit = max(performance.max_profit or 0, pnl_percent)
            performance.max_loss = min(performance.max_loss or 0, pnl_percent)

            # Handle exit
            if exit_price is not None:
                performance.exit_price = exit_price
                performance.realized_pnl = pnl_percent
                performance.is_active = False
                performance.exit_reason = exit_reason or "manual_exit"

                # Calculate hold duration
                hold_duration = (
                    datetime.utcnow() - performance.created_at
                ).total_seconds() / 3600
                performance.hold_duration_hours = hold_duration

                # Determine outcome
                if pnl_percent > 1:
                    performance.outcome = "profitable"
                elif pnl_percent < -1:
                    performance.outcome = "loss"
                else:
                    performance.outcome = "breakeven"

                logger.info(f"Closed signal {signal_id} with {pnl_percent:.2f}% P&L")

            return True

        except SQLAlchemyError as e:
            logger.error(f"Error updating signal performance: {e}")
            session.rollback()
            raise

    # =============================================================================
    # TECHNICAL INDICATORS CACHING
    # =============================================================================

    @staticmethod
    def cache_technical_indicators(
        session: Session,
        symbol: str,
        timeframe: str,
        timestamp: datetime,
        indicators: Dict[str, float],
    ) -> TechnicalIndicators:
        """Cache calculated technical indicators"""
        try:
            # Check if record already exists
            existing = (
                session.query(TechnicalIndicators)
                .filter(
                    TechnicalIndicators.symbol == symbol,
                    TechnicalIndicators.timeframe == timeframe,
                    TechnicalIndicators.timestamp == timestamp,
                )
                .first()
            )

            if existing:
                # Update existing record
                for key, value in indicators.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
                return existing
            else:
                # Create new record
                tech_indicator = TechnicalIndicators(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=timestamp,
                    **indicators,
                )
                session.add(tech_indicator)
                return tech_indicator

        except SQLAlchemyError as e:
            logger.error(f"Error caching technical indicators: {e}")
            session.rollback()
            raise

    @staticmethod
    def get_cached_indicators(
        session: Session, symbol: str, timeframe: str, hours_back: int = 24
    ) -> List[TechnicalIndicators]:
        """Get cached technical indicators"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        return (
            session.query(TechnicalIndicators)
            .filter(
                TechnicalIndicators.symbol == symbol,
                TechnicalIndicators.timeframe == timeframe,
                TechnicalIndicators.timestamp >= cutoff_time,
            )
            .order_by(TechnicalIndicators.timestamp.desc())
            .all()
        )

    # =============================================================================
    # SYSTEM LOGGING OPERATIONS
    # =============================================================================

    @staticmethod
    def log_system_event(
        session: Session,
        symbol: str,
        event_type: str,
        details: str = None,
        confidence: str = None,
        price: float = None,
    ) -> SystemLog:
        """Log system events with standardized format"""
        try:
            log_entry = SystemLog(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                event_type=event_type,
                details=details,
                confidence=confidence,
                price=price,
            )

            session.add(log_entry)
            return log_entry

        except SQLAlchemyError as e:
            logger.error(f"Error logging system event: {e}")
            session.rollback()
            raise

    @staticmethod
    def get_system_events(
        session: Session,
        hours: int = 24,
        event_types: List[str] = None,
        symbols: List[str] = None,
    ) -> List[SystemLog]:
        """Get system events with optional filters"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = session.query(SystemLog).filter(SystemLog.timestamp >= cutoff_time)

        if event_types:
            query = query.filter(SystemLog.event_type.in_(event_types))

        if symbols:
            query = query.filter(SystemLog.symbol.in_(symbols))

        return query.order_by(SystemLog.timestamp.desc()).all()

    # =============================================================================
    # MONITORING AND SYMBOL MANAGEMENT
    # =============================================================================

    @staticmethod
    def set_monitored_symbols(
        session: Session, symbols: List[str], monitored: bool = True
    ) -> int:
        """Set symbols as monitored/unmonitored"""
        try:
            count = 0

            for symbol in symbols:
                crypto = session.query(Crypto).filter(Crypto.symbol == symbol).first()

                if crypto:
                    crypto.monitored = monitored
                    count += 1
                else:
                    # Create new crypto entry
                    new_crypto = Crypto(symbol=symbol, monitored=monitored)
                    session.add(new_crypto)
                    count += 1

            logger.info(f"Set {count} symbols monitoring status to {monitored}")
            return count

        except SQLAlchemyError as e:
            logger.error(f"Error setting monitored symbols: {e}")
            session.rollback()
            raise

    @staticmethod
    def get_monitored_symbols(session: Session) -> List[str]:
        """Get list of monitored symbols"""
        symbols = session.query(Crypto.symbol).filter(Crypto.monitored == True).all()
        return [symbol[0] for symbol in symbols]

    # =============================================================================
    # DATA CLEANUP OPERATIONS
    # =============================================================================

    @staticmethod
    def cleanup_old_data(session: Session, days_to_keep: int = 90) -> Dict[str, int]:
        """Clean up old data while preserving important records"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            cleanup_stats = {}

            # Clean up old system log entries (except signals)
            deleted_logs = (
                session.query(SystemLog)
                .filter(
                    SystemLog.timestamp < cutoff_date,
                    ~SystemLog.event_type.like("%SIGNAL%"),
                )
                .delete(synchronize_session=False)
            )
            cleanup_stats["system_logs"] = deleted_logs

            # Clean up expired alerts older than cutoff
            deleted_alerts = (
                session.query(AlertStates)
                .filter(
                    AlertStates.updated_at < cutoff_date,
                    AlertStates.status.in_(["expired", "triggered"]),
                )
                .delete(synchronize_session=False)
            )
            cleanup_stats["expired_alerts"] = deleted_alerts

            # Clean up old technical indicator cache
            deleted_indicators = (
                session.query(TechnicalIndicators)
                .filter(TechnicalIndicators.timestamp < cutoff_date)
                .delete(synchronize_session=False)
            )
            cleanup_stats["technical_indicators"] = deleted_indicators

            logger.info(f"Cleanup completed: {cleanup_stats}")
            return cleanup_stats

        except SQLAlchemyError as e:
            logger.error(f"Error during data cleanup: {e}")
            session.rollback()
            raise

    # =============================================================================
    # ANALYTICAL QUERIES
    # =============================================================================

    @staticmethod
    def get_alert_conversion_rates(session: Session, days: int = 30) -> Dict[str, Any]:
        """Calculate alert-to-signal conversion rates"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Total alerts created
        total_alerts = (
            session.query(AlertStates)
            .filter(AlertStates.created_at >= cutoff_date)
            .count()
        )

        # Alerts that generated signals
        triggered_alerts = (
            session.query(AlertStates)
            .filter(
                AlertStates.created_at >= cutoff_date, AlertStates.status == "triggered"
            )
            .count()
        )

        # Expired alerts
        expired_alerts = (
            session.query(AlertStates)
            .filter(
                AlertStates.created_at >= cutoff_date, AlertStates.status == "expired"
            )
            .count()
        )

        # Conversion rate by alert type
        alert_type_stats = (
            session.query(
                AlertStates.alert_type,
                func.count(AlertStates.id).label("total"),
                func.sum(
                    func.case([(AlertStates.status == "triggered", 1)], else_=0)
                ).label("triggered"),
            )
            .filter(AlertStates.created_at >= cutoff_date)
            .group_by(AlertStates.alert_type)
            .all()
        )

        conversion_rate = (
            (triggered_alerts / total_alerts * 100) if total_alerts > 0 else 0
        )

        return {
            "period_days": days,
            "total_alerts": total_alerts,
            "triggered_alerts": triggered_alerts,
            "expired_alerts": expired_alerts,
            "conversion_rate_percent": round(conversion_rate, 2),
            "by_alert_type": [
                {
                    "type": alert_type,
                    "total": total,
                    "triggered": triggered,
                    "conversion_rate": round(
                        (triggered / total * 100) if total > 0 else 0, 2
                    ),
                }
                for alert_type, total, triggered in alert_type_stats
            ],
        }

    @staticmethod
    def get_symbol_performance_ranking(
        session: Session, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get performance ranking by symbol"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        symbol_stats = (
            session.query(
                TradingSignals.symbol,
                func.count(TradingSignals.id).label("total_signals"),
                func.avg(SignalPerformance.pnl_percent).label("avg_pnl"),
                func.count(SignalPerformance.id).label("tracked_signals"),
            )
            .outerjoin(
                SignalPerformance, TradingSignals.id == SignalPerformance.signal_id
            )
            .filter(TradingSignals.created_at >= cutoff_date)
            .group_by(TradingSignals.symbol)
            .order_by(func.avg(SignalPerformance.pnl_percent).desc())
            .all()
        )

        return [
            {
                "symbol": symbol,
                "total_signals": total_signals,
                "tracked_signals": tracked_signals,
                "avg_pnl_percent": round(float(avg_pnl), 2) if avg_pnl else None,
            }
            for symbol, total_signals, avg_pnl, tracked_signals in symbol_stats
        ]
