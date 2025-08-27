# data/repositories/historical_repository.py
"""
Historical price data repository
Specialized operations for OHLCV candlestick data
"""

from typing import List, Optional, Tuple, Dict
from sqlalchemy import desc, and_, func
from datetime import datetime, timedelta

from .base_repository import BaseRepository
from database.models import Historical


class HistoricalRepository(BaseRepository[Historical]):
    """Repository for historical price data"""

    def __init__(self, db_manager):
        super().__init__(db_manager, Historical)

    def get_recent_data(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> List[Historical]:
        """Get recent historical data for a symbol and timeframe"""
        with self.get_session() as session:
            # Map timeframe to interval_minutes for compatibility
            interval_map = {"15min": 15, "1hour": 60, "1day": 1440}
            interval_minutes = interval_map.get(timeframe, 15)

            return (
                session.query(Historical)
                .filter(
                    and_(
                        Historical.symbol == symbol,
                        Historical.interval_minutes == interval_minutes,
                    )
                )
                .order_by(desc(Historical.timestamp))
                .limit(limit)
                .all()
            )

    def get_latest_timestamp(
        self, symbol: str, interval_minutes: int
    ) -> Optional[datetime]:
        """Get the latest timestamp for a symbol/interval combination"""
        with self.get_session() as session:
            result = (
                session.query(func.max(Historical.timestamp))
                .filter(
                    and_(
                        Historical.symbol == symbol,
                        Historical.interval_minutes == interval_minutes,
                    )
                )
                .scalar()
            )

            return result

    def get_data_range(
        self,
        symbol: str,
        interval_minutes: int,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Historical]:
        """Get historical data within a time range"""
        with self.get_session() as session:
            return (
                session.query(Historical)
                .filter(
                    and_(
                        Historical.symbol == symbol,
                        Historical.interval_minutes == interval_minutes,
                        Historical.timestamp >= start_time,
                        Historical.timestamp <= end_time,
                    )
                )
                .order_by(Historical.timestamp)
                .all()
            )

    def bulk_insert(self, historical_data: List[Dict]) -> int:
        """
        Bulk insert historical data records, skipping duplicates based on
        symbol, timestamp, and interval_minutes
        """
        if not historical_data:
            return 0

        with self.get_session() as session:
            # Get all unique combinations of (symbol, timestamp, interval_minutes) from input data
            input_keys = set()
            records_to_insert = []

            for data in historical_data:
                key = (data["symbol"], data["timestamp"], data["interval_minutes"])
                if key not in input_keys:  # Also deduplicate within the input data
                    input_keys.add(key)
                    records_to_insert.append(data)

            if not records_to_insert:
                return 0

            # Query existing records that match any of our input combinations
            # Build conditions for each (symbol, timestamp, interval_minutes) combination
            from sqlalchemy import and_, or_

            conditions = []
            for symbol, timestamp, interval_minutes in input_keys:
                condition = and_(
                    Historical.symbol == symbol,
                    Historical.timestamp == timestamp,
                    Historical.interval_minutes == interval_minutes,
                )
                conditions.append(condition)

            # Query existing records in batches to avoid query size limits
            existing_keys = set()
            batch_size = 500  # Process in batches to avoid large IN clauses

            for i in range(0, len(conditions), batch_size):
                batch_conditions = conditions[i : i + batch_size]

                existing_records = (
                    session.query(
                        Historical.symbol,
                        Historical.timestamp,
                        Historical.interval_minutes,
                    )
                    .filter(or_(*batch_conditions))
                    .all()
                )

                # Add to existing keys set
                for record in existing_records:
                    existing_keys.add(
                        (record.symbol, record.timestamp, record.interval_minutes)
                    )

            # Filter out records that already exist
            new_records = []
            for data in records_to_insert:
                key = (data["symbol"], data["timestamp"], data["interval_minutes"])
                if key not in existing_keys:
                    new_records.append(Historical(**data))

            # Bulk insert only new records
            if new_records:
                session.bulk_save_objects(new_records)
                self.logger.info(
                    f"Inserted {len(new_records)} new records, skipped {len(records_to_insert) - len(new_records)} duplicates"
                )
            else:
                self.logger.info(
                    f"All {len(records_to_insert)} records already exist, skipped all"
                )

            return len(new_records)

    def delete_old_data(self, days_back: int) -> int:
        """Delete historical data older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        with self.get_session() as session:
            deleted = (
                session.query(Historical)
                .filter(Historical.timestamp < cutoff_date)
                .delete()
            )

            return deleted

    def get_data_gaps(
        self, symbol: str, interval_minutes: int, expected_interval_minutes: int
    ) -> List[Tuple[datetime, datetime]]:
        """Identify gaps in historical data"""
        gaps = []

        with self.get_session() as session:
            # Get all timestamps for the symbol/interval ordered by time
            timestamps = (
                session.query(Historical.timestamp)
                .filter(
                    and_(
                        Historical.symbol == symbol,
                        Historical.interval_minutes == interval_minutes,
                    )
                )
                .order_by(Historical.timestamp)
                .all()
            )

            if len(timestamps) < 2:
                return gaps

            expected_delta = timedelta(minutes=expected_interval_minutes)

            for i in range(1, len(timestamps)):
                prev_time = timestamps[i - 1][0]
                curr_time = timestamps[i][0]

                # Check if gap is larger than expected interval
                actual_delta = curr_time - prev_time
                if actual_delta > expected_delta * 1.5:  # Allow 50% tolerance
                    gaps.append((prev_time, curr_time))

        return gaps
