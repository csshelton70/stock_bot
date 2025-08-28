# ./database/models.py
"""
SQLAlchemy models for Robinhood Crypto Trading App
ENHANCED: Strengthened unique constraints and validation for Historical table
"""
# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation, import-outside-toplevel

from typing import Dict, Any

from datetime import datetime, timedelta

from .crypto import Crypto
from .alert_states import AlertStates
from .system_log import SystemLog
from .historical import Historical


from utils.logger import get_logger

logger = get_logger(__name__)


def get_monitored_crypto_symbols(session) -> list:
    """ 
    """
    try:
        return [
            crypto.symbol
            for crypto in session.query(Crypto).filter(Crypto.monitored).all()
        ]
    except Exception as e:
        logger.error(f"Error getting monitored symbols: {e}")  # ✅ FIXED
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
        get_logger(__name__).error(f"Error getting alerts for {symbol}: {e}")
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
        get_logger(__name__).error(f"Error getting recent events: {e}")
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
        get_logger(__name__).error(f"Error cleaning up expired alerts: {e}")
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
        get_logger(__name__).error(f"Error validating historical data integrity: {e}")
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


        get_logger(__name__).error(f"Error generating coverage report: {e}")
        return {"error": str(e)}
