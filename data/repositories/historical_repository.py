# data/repositories/historical_repository.py
"""
Historical price data repository
Specialized operations for OHLCV candlestick data
"""

from typing import List, Optional, Tuple, Dict, Set, Any
from sqlalchemy import desc, and_, func, or_
from datetime import datetime, timedelta

from .base_repository import BaseRepository
from database.models import Historical


class HistoricalRepository(BaseRepository[Historical]):
    """Repository for historical price data with efficient duplicate handling"""

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
        Bulk insert historical data records with efficient duplicate checking
        FIXED: Uses optimized EXISTS queries to prevent duplicates
        """
        if not historical_data:
            return 0

        with self.get_session() as session:
            # Deduplicate input data first
            seen_keys = set()
            unique_records = []

            for data in historical_data:
                key = (data["symbol"], data["timestamp"], data["interval_minutes"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    unique_records.append(data)

            if not unique_records:
                self.logger.info("No unique records to insert after deduplication")
                return 0

            self.logger.info(
                f"Deduplicated {len(historical_data)} records to {len(unique_records)}"
            )

            # Check existing records efficiently using batch queries
            existing_keys = self._get_existing_keys_batch(session, unique_records)

            # Filter out existing records
            new_records = []
            for data in unique_records:
                key = (data["symbol"], data["timestamp"], data["interval_minutes"])
                if key not in existing_keys:
                    new_records.append(Historical(**data))

            # Bulk insert only new records
            if new_records:
                try:
                    session.bulk_save_objects(new_records)
                    session.flush()

                    self.logger.info(
                        f"Successfully inserted {len(new_records)} new records, "
                        f"skipped {len(unique_records) - len(new_records)} duplicates"
                    )
                except Exception as e:
                    self.logger.error(f"Bulk insert failed: {e}")
                    # Fallback to individual inserts with explicit duplicate checking
                    return self._insert_individually_with_checking(
                        session, unique_records
                    )
            else:
                self.logger.info(
                    f"All {len(unique_records)} records already exist, skipped all"
                )

            return len(new_records)

    def _get_existing_keys_batch(self, session, records: List[Dict]) -> Set[Tuple]:
        """
        Efficiently get existing record keys using batch queries
        FIXED: Uses optimized batch checking to reduce database queries
        """
        existing_keys = set()

        # Group records by symbol to optimize queries
        symbol_groups = {}
        for record in records:
            symbol = record["symbol"]
            if symbol not in symbol_groups:
                symbol_groups[symbol] = []
            symbol_groups[symbol].append(record)

        # Query each symbol group separately for better performance
        for symbol, symbol_records in symbol_groups.items():
            # Get min and max timestamps for this symbol
            timestamps = [r["timestamp"] for r in symbol_records]
            min_time = min(timestamps)
            max_time = max(timestamps)

            # Get interval_minutes values for this symbol
            intervals = list(set(r["interval_minutes"] for r in symbol_records))

            # Single query per symbol to get all existing records in range
            existing_records = (
                session.query(
                    Historical.symbol, Historical.timestamp, Historical.interval_minutes
                )
                .filter(
                    and_(
                        Historical.symbol == symbol,
                        Historical.timestamp >= min_time,
                        Historical.timestamp <= max_time,
                        Historical.interval_minutes.in_(intervals),
                    )
                )
                .all()
            )

            # Add to existing keys set
            for record in existing_records:
                existing_keys.add(
                    (record.symbol, record.timestamp, record.interval_minutes)
                )

        return existing_keys

    def _insert_individually_with_checking(self, session, records: List[Dict]) -> int:
        """
        Fallback method to insert records individually with explicit duplicate checking
        FIXED: Uses EXISTS subquery for efficient duplicate checking
        """
        inserted_count = 0

        for data in records:
            try:
                # Use EXISTS subquery for efficient duplicate checking
                exists_query = session.query(
                    session.query(Historical)
                    .filter(
                        and_(
                            Historical.symbol == data["symbol"],
                            Historical.timestamp == data["timestamp"],
                            Historical.interval_minutes == data["interval_minutes"],
                        )
                    )
                    .exists()
                ).scalar()

                if not exists_query:
                    historical_record = Historical(**data)
                    session.add(historical_record)
                    inserted_count += 1

                    # Flush every 100 records to avoid memory buildup
                    if inserted_count % 100 == 0:
                        session.flush()

            except Exception as e:
                self.logger.debug(f"Skipping record due to error: {e}")
                continue

        # Final flush
        if inserted_count > 0:
            session.flush()

        self.logger.info(
            f"Individual insert completed: {inserted_count} records inserted"
        )
        return inserted_count

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

    def get_record_count_by_symbol(self, symbol: str, days: int = 30) -> Dict[str, int]:
        """Get record counts by interval for a symbol"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        with self.get_session() as session:
            results = (
                session.query(
                    Historical.interval_minutes,
                    func.count(Historical.id).label("count"),
                )
                .filter(
                    and_(
                        Historical.symbol == symbol, Historical.timestamp >= cutoff_date
                    )
                )
                .group_by(Historical.interval_minutes)
                .all()
            )

            return {f"{interval}min": count for interval, count in results}

    def check_data_integrity(
        self, symbol: str, interval_minutes: int
    ) -> Dict[str, Any]:
        """Check data integrity for a symbol/interval combination"""
        with self.get_session() as session:
            # Get basic statistics
            stats = (
                session.query(
                    func.count(Historical.id).label("total_records"),
                    func.min(Historical.timestamp).label("earliest"),
                    func.max(Historical.timestamp).label("latest"),
                )
                .filter(
                    and_(
                        Historical.symbol == symbol,
                        Historical.interval_minutes == interval_minutes,
                    )
                )
                .first()
            )

            # Check for potential gaps
            gaps = self.get_data_gaps(symbol, interval_minutes, interval_minutes)

            # Calculate expected vs actual records (rough estimate)
            if stats.earliest and stats.latest:
                time_span = stats.latest - stats.earliest
                expected_records = int(
                    time_span.total_seconds() / (interval_minutes * 60)
                )
                data_completeness = (
                    (stats.total_records / expected_records * 100)
                    if expected_records > 0
                    else 0
                )
            else:
                expected_records = 0
                data_completeness = 0

            return {
                "symbol": symbol,
                "interval_minutes": interval_minutes,
                "total_records": stats.total_records,
                "earliest_timestamp": stats.earliest,
                "latest_timestamp": stats.latest,
                "data_gaps": len(gaps),
                "expected_records": expected_records,
                "data_completeness_percent": round(data_completeness, 2),
            }
