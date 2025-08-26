#!/usr/bin/env python3
"""
Improved Database Operations for Robinhood Crypto Trading App
Enhanced with Trading System operations and better error handling
"""

import logging
import pandas as pd
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, desc, func, text

# Import models - assuming they are in database.models
try:
    from database.models import (
        Crypto,
        Account,
        Holdings,
        Historical,
        AlertStates,
        SystemLog,
    )
except ImportError:
    # Fallback import structure
    from models import Crypto, Account, Holdings, Historical, AlertStates, SystemLog

logger = logging.getLogger("database_operations")


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
    def bulk_insert_historical_data(
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

    # =============================================================================
    # TRADING SYSTEM OPERATIONS
    # =============================================================================

    @staticmethod
    def get_monitored_symbols(session: Session) -> List[str]:
        """Get list of symbols marked as monitored"""
        try:
            result = session.query(Crypto.symbol).filter(Crypto.monitored == True).all()
            symbols = [row[0] for row in result]
            logger.debug(f"Found {len(symbols)} monitored symbols")
            return symbols
        except Exception as e:
            logger.error(f"Error getting monitored symbols: {e}")
            return []

    @staticmethod
    def get_active_alerts(session: Session, symbol: str = None) -> List[AlertStates]:
        """Get active alert states with optional symbol filter"""
        try:
            query = session.query(AlertStates).filter(AlertStates.status == "active")

            if symbol:
                query = query.filter(AlertStates.symbol == symbol)

            alerts = query.order_by(AlertStates.start_time.desc()).all()
            logger.debug(f"Found {len(alerts)} active alerts")
            return alerts

        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []

    @staticmethod
    def create_alert(
        session: Session,
        symbol: str,
        alert_type: str,
        rsi_value: float,
        trigger_level: float,
    ) -> bool:
        """Create new alert state with validation"""
        try:
            # Validate inputs
            if not symbol or not alert_type:
                logger.error("Symbol and alert_type are required")
                return False

            if alert_type not in ["buy", "sell"]:
                logger.error(f"Invalid alert_type: {alert_type}")
                return False

            # Check for existing active alert
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
                logger.debug(f"Alert already active for {symbol} {alert_type}")
                return False

            # Create new alert
            new_alert = AlertStates(
                symbol=symbol,
                alert_type=alert_type,
                start_time=datetime.utcnow(),
                rsi_trigger_level=trigger_level,
                initial_rsi=rsi_value,
                status="active",
            )

            session.add(new_alert)
            session.flush()

            logger.info(
                f"Created {alert_type} alert for {symbol} (RSI: {rsi_value:.1f})"
            )
            return True

        except Exception as e:
            logger.error(f"Error creating alert for {symbol}: {e}")
            return False

    @staticmethod
    def update_alert_status(session: Session, alert_id: int, new_status: str) -> bool:
        """Update alert status with validation"""
        try:
            if new_status not in ["active", "triggered", "expired"]:
                logger.error(f"Invalid status: {new_status}")
                return False

            alert = (
                session.query(AlertStates).filter(AlertStates.id == alert_id).first()
            )

            if not alert:
                logger.warning(f"Alert {alert_id} not found")
                return False

            old_status = alert.status
            alert.status = new_status
            alert.updated_at = datetime.utcnow()
            session.flush()

            logger.debug(
                f"Updated alert {alert_id} status: {old_status} -> {new_status}"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating alert {alert_id} status: {e}")
            return False

    @staticmethod
    def expire_old_alerts(session: Session, timeout_hours: int = 12) -> int:
        """Expire alerts older than timeout period"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=timeout_hours)

            old_alerts = (
                session.query(AlertStates)
                .filter(
                    AlertStates.status == "active", AlertStates.start_time < cutoff_time
                )
                .all()
            )

            count = 0
            for alert in old_alerts:
                alert.status = "expired"
                alert.updated_at = datetime.utcnow()
                count += 1

            if count > 0:
                session.flush()
                logger.info(f"Expired {count} old alerts")

            return count

        except Exception as e:
            logger.error(f"Error expiring old alerts: {e}")
            return 0

    @staticmethod
    def log_system_event(
        session: Session,
        symbol: str,
        event_type: str,
        details: str = None,
        confidence: str = None,
        price: float = None,
    ) -> bool:
        """Log system event with validation"""
        try:
            # Validate required fields
            if not symbol or not event_type:
                logger.error("Symbol and event_type are required for logging")
                return False

            # Validate confidence if provided
            if confidence and confidence not in ["HIGH", "MEDIUM", "LOW", "REJECT"]:
                logger.warning(f"Invalid confidence level: {confidence}")
                confidence = None

            log_entry = SystemLog(
                symbol=symbol,
                event_type=event_type,
                details=details,
                confidence=confidence,
                price=price,
                timestamp=datetime.utcnow(),
            )

            session.add(log_entry)
            session.flush()
            return True

        except Exception as e:
            logger.error(f"Error logging event: {e}")
            return False

    @staticmethod
    def get_system_logs(
        session: Session,
        symbol: str = None,
        event_type: str = None,
        hours_back: int = 24,
        limit: int = 100,
    ) -> List[SystemLog]:
        """Get system log entries with filtering"""
        try:
            query = session.query(SystemLog)

            # Apply time filter
            if hours_back > 0:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
                query = query.filter(SystemLog.timestamp >= cutoff_time)

            # Apply symbol filter
            if symbol:
                query = query.filter(SystemLog.symbol == symbol)

            # Apply event type filter
            if event_type:
                query = query.filter(SystemLog.event_type.like(f"%{event_type}%"))

            # Order and limit
            logs = query.order_by(SystemLog.timestamp.desc()).limit(limit).all()

            logger.debug(f"Retrieved {len(logs)} log entries")
            return logs

        except Exception as e:
            logger.error(f"Error getting system logs: {e}")
            return []

    @staticmethod
    def get_alert_history(
        session: Session, symbol: str = None, days_back: int = 7
    ) -> List[AlertStates]:
        """Get alert history with filtering"""
        try:
            query = session.query(AlertStates)

            # Apply time filter
            if days_back > 0:
                cutoff_time = datetime.utcnow() - timedelta(days=days_back)
                query = query.filter(AlertStates.created_at >= cutoff_time)

            # Apply symbol filter
            if symbol:
                query = query.filter(AlertStates.symbol == symbol)

            alerts = query.order_by(AlertStates.start_time.desc()).all()

            logger.debug(f"Retrieved {len(alerts)} alert history records")
            return alerts

        except Exception as e:
            logger.error(f"Error getting alert history: {e}")
            return []

    @staticmethod
    def cleanup_old_system_logs(session: Session, days_to_keep: int = 30) -> int:
        """Clean up old log entries"""
        try:
            if days_to_keep <= 0:
                logger.warning("Invalid days_to_keep value, using default of 30")
                days_to_keep = 30

            cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)

            # Count old logs first
            old_logs_count = (
                session.query(SystemLog)
                .filter(SystemLog.timestamp < cutoff_time)
                .count()
            )

            if old_logs_count == 0:
                logger.info("No old logs to clean up")
                return 0

            # Delete old logs
            deleted_count = (
                session.query(SystemLog)
                .filter(SystemLog.timestamp < cutoff_time)
                .delete(synchronize_session=False)
            )

            session.flush()
            logger.info(f"Cleaned up {deleted_count} old log entries")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")
            return 0

    @staticmethod
    def reset_all_alerts(session: Session) -> int:
        """Reset all active alerts (emergency function)"""
        try:
            # Count active alerts first
            active_count = (
                session.query(AlertStates)
                .filter(AlertStates.status == "active")
                .count()
            )

            if active_count == 0:
                logger.info("No active alerts to reset")
                return 0

            # Update all active alerts to expired
            updated_count = (
                session.query(AlertStates)
                .filter(AlertStates.status == "active")
                .update(
                    {"status": "expired", "updated_at": datetime.utcnow()},
                    synchronize_session=False,
                )
            )

            session.flush()
            logger.warning(f"Reset {updated_count} active alerts")
            return updated_count

        except Exception as e:
            logger.error(f"Error resetting alerts: {e}")
            return 0

    # =============================================================================
    # DATA ANALYSIS AND MONITORING OPERATIONS
    # =============================================================================

    @staticmethod
    def get_historical_data_summary(session: Session) -> Dict[str, Dict]:
        """Get summary of available historical data"""
        try:
            # Use raw SQL for better performance
            query = text(
                """
                SELECT 
                    h.symbol,
                    COUNT(*) as record_count,
                    MIN(h.timestamp) as earliest_date,
                    MAX(h.timestamp) as latest_date,
                    h.interval_minutes,
                    c.monitored
                FROM historical h
                LEFT JOIN crypto c ON h.symbol = c.symbol
                GROUP BY h.symbol, h.interval_minutes
                ORDER BY record_count DESC
            """
            )

            results = session.execute(query).fetchall()

            data_summary = {}
            for row in results:
                symbol = row.symbol

                if symbol not in data_summary:
                    data_summary[symbol] = {
                        "timeframes": {},
                        "is_monitored": (
                            bool(row.monitored) if row.monitored is not None else False
                        ),
                    }

                # Calculate coverage metrics
                if row.earliest_date and row.latest_date:
                    earliest_dt = row.earliest_date
                    latest_dt = row.latest_date

                    if isinstance(earliest_dt, str):
                        earliest_dt = datetime.fromisoformat(earliest_dt)
                        latest_dt = datetime.fromisoformat(latest_dt)

                    days_coverage = (latest_dt - earliest_dt).days
                    hours_since_update = (
                        datetime.now() - latest_dt
                    ).total_seconds() / 3600
                else:
                    days_coverage = 0
                    hours_since_update = None

                data_summary[symbol]["timeframes"][f"{row.interval_minutes}min"] = {
                    "record_count": row.record_count,
                    "earliest_date": row.earliest_date,
                    "latest_date": row.latest_date,
                    "days_coverage": days_coverage,
                    "hours_since_update": hours_since_update,
                    "is_recent": (
                        hours_since_update < 24 if hours_since_update else False
                    ),
                }

            logger.debug(f"Generated summary for {len(data_summary)} symbols")
            return data_summary

        except Exception as e:
            logger.error(f"Error getting historical data summary: {e}")
            return {}

    @staticmethod
    def get_crypto_table_status(session: Session) -> Dict:
        """Get crypto table status and monitoring info"""
        try:
            total_symbols = session.query(Crypto).count()
            monitored_symbols = (
                session.query(Crypto).filter(Crypto.monitored == True).count()
            )

            # Get symbols with recent updates
            recent_cutoff = datetime.now() - timedelta(hours=2)
            recent_updates = (
                session.query(Crypto).filter(Crypto.updated_at >= recent_cutoff).count()
            )

            # Get price coverage
            symbols_with_prices = (
                session.query(Crypto).filter(Crypto.mid.isnot(None)).count()
            )

            return {
                "total_symbols": total_symbols,
                "monitored_symbols": monitored_symbols,
                "recent_updates": recent_updates,
                "symbols_with_prices": symbols_with_prices,
                "monitoring_rate": (
                    monitored_symbols / total_symbols if total_symbols > 0 else 0
                ),
                "price_coverage": (
                    symbols_with_prices / total_symbols if total_symbols > 0 else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error getting crypto table status: {e}")
            return {}

    @staticmethod
    def set_monitoring_flags(
        session: Session, symbols: List[str], monitored: bool = True
    ) -> int:
        """Set monitoring flags for specified symbols"""
        try:
            if not symbols and monitored:
                logger.warning("No symbols provided for monitoring")
                return 0

            count = 0

            if not monitored:
                # Reset all monitoring flags
                updated = session.query(Crypto).update(
                    {"monitored": False}, synchronize_session=False
                )
                count = updated
                logger.info(f"Reset monitoring for all {count} symbols")
            else:
                # Set monitoring for specific symbols
                for symbol in symbols:
                    updated = (
                        session.query(Crypto)
                        .filter(Crypto.symbol == symbol)
                        .update({"monitored": True}, synchronize_session=False)
                    )
                    if updated > 0:
                        count += updated

                logger.info(f"Set monitoring for {count} symbols")

            session.flush()
            return count

        except Exception as e:
            logger.error(f"Error setting monitoring flags: {e}")
            return 0

    @staticmethod
    def get_symbols_by_strategy(session: Session, strategy: str) -> List[str]:
        """Get symbols based on monitoring strategy"""
        try:
            if strategy == "holdings":
                # Get symbols with current holdings
                query = text(
                    """
                    SELECT DISTINCT h.symbol
                    FROM holdings h
                    WHERE h.total_quantity > 0
                """
                )

            elif strategy == "top_volume":
                # Get top symbols by recent volume
                query = text(
                    """
                    SELECT h.symbol
                    FROM historical h
                    WHERE h.timestamp > datetime('now', '-7 days')
                      AND h.volume > 0
                    GROUP BY h.symbol
                    ORDER BY AVG(h.volume) DESC
                    LIMIT 10
                """
                )

            elif strategy == "major_pairs":
                # Return predefined major pairs
                return [
                    "BTC-USD",
                    "ETH-USD",
                    "ADA-USD",
                    "SOL-USD",
                    "DOGE-USD",
                    "MATIC-USD",
                    "DOT-USD",
                    "LINK-USD",
                    "UNI-USD",
                    "LTC-USD",
                ]

            elif strategy == "active_trading":
                # Get symbols with recent price movement
                query = text(
                    """
                    SELECT h.symbol
                    FROM historical h
                    WHERE h.timestamp > datetime('now', '-3 days')
                    GROUP BY h.symbol
                    HAVING COUNT(*) > 100
                       AND (MAX(h.high) - MIN(h.low)) / AVG(h.close) > 0.05
                    ORDER BY (MAX(h.high) - MIN(h.low)) / AVG(h.close) DESC
                    LIMIT 15
                """
                )

            else:
                logger.error(f"Unknown monitoring strategy: {strategy}")
                return []

            if strategy != "major_pairs":
                results = session.execute(query).fetchall()
                symbols = [row[0] for row in results]
            else:
                symbols = ["BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD", "DOGE-USD"]

            logger.info(f"Strategy '{strategy}' returned {len(symbols)} symbols")
            return symbols

        except Exception as e:
            logger.error(f"Error getting symbols by strategy {strategy}: {e}")
            return []

    # =============================================================================
    # UTILITY OPERATIONS
    # =============================================================================

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
