# collectors/historical_collector.py
"""
Refactored Historical Collector using the new base collector architecture
Collects historical OHLCV candlestick data from Coinbase API
FIXED: Enhanced duplicate prevention and error handling
"""

import time
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from sqlalchemy import and_


from .base_collector import BaseCollector
from database.connections import DatabaseManager
from database.models import Historical, Crypto
from data.repositories.historical_repository import HistoricalRepository
from data.repositories.crypto_repository import CryptoRepository
from utils.retry import RetryConfig
from database import DatabaseSession


class HistoricalCollector(BaseCollector):
    """
    Refactored historical collector using repository pattern
    Collects OHLCV data from Coinbase Exchange API
    FIXED: Enhanced duplicate prevention and data integrity
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        retry_config: RetryConfig,
        historical_repo: HistoricalRepository,
        crypto_repo: CryptoRepository,
        days_back: int = 60,
        interval_minutes: int = 15,
        buffer_days: int = 1,
    ):
        super().__init__(db_manager, retry_config)
        self.historical_repo = historical_repo
        self.crypto_repo = crypto_repo
        self.days_back = days_back
        self.interval_minutes = interval_minutes
        self.buffer_days = buffer_days
        self.request_delay = 0.5  # Base delay between API requests
        self.max_request_delay = 5.0

        # Coinbase API endpoint
        self.coinbase_base_url = "https://api.exchange.coinbase.com"

    def get_collector_name(self) -> str:
        return f"Historical Price Data ({self.interval_minutes}min intervals)"

    def collect_and_store(self) -> bool:
        """Main collection logic using repository pattern - FIXED"""
        try:
            # Get monitored symbols
            monitored_symbols = self._get_monitored_symbols()

            if not monitored_symbols:
                self.logger.warning("No monitored symbols found")
                return True  # Not an error, just nothing to collect

            self.logger.info(
                f"Collecting historical data for {len(monitored_symbols)} symbols"
            )

            collection_stats = {
                "symbols_processed": 0,
                "records_inserted": 0,
                "records_skipped": 0,
                "symbols_with_errors": 0,
                "api_requests_made": 0,
            }

            # Process each monitored symbol
            for symbol in monitored_symbols:
                try:
                    symbol_stats = self._collect_symbol_data(symbol)
                    collection_stats["symbols_processed"] += 1
                    collection_stats["records_inserted"] += symbol_stats.get(
                        "inserted", 0
                    )
                    collection_stats["records_skipped"] += symbol_stats.get(
                        "skipped", 0
                    )
                    collection_stats["api_requests_made"] += symbol_stats.get(
                        "api_requests", 0
                    )

                    self.logger.info(
                        f"{symbol}: {symbol_stats.get('inserted', 0)} inserted, "
                        f"{symbol_stats.get('skipped', 0)} skipped duplicates"
                    )

                    # Rate limiting delay
                    time.sleep(self.request_delay)

                except Exception as e:
                    self.logger.error(f"Error collecting data for {symbol}: {e}")
                    collection_stats["symbols_with_errors"] += 1
                    continue

            # Log collection statistics
            self.log_collection_stats(collection_stats)

            return collection_stats["symbols_with_errors"] == 0

        except Exception as e:
            self.logger.error(f"Historical collection failed: {e}")
            return False

    def _get_monitored_symbols(self) -> List[str]:
        """Get list of monitored symbols from crypto repository"""
        try:
            return self.crypto_repo.get_monitored_symbols()
        except Exception as e:
            self.logger.error(f"Error getting monitored symbols: {e}")
            return []

    def _collect_symbol_data(self, symbol: str) -> Dict[str, int]:
        """
        Collect historical data for a single symbol - FIXED
        Returns statistics about records inserted vs skipped
        """
        try:
            # Check if we have existing data
            latest_timestamp = self.historical_repo.get_latest_timestamp(
                symbol, self.interval_minutes
            )

            stats = {"inserted": 0, "skipped": 0, "api_requests": 0}

            if latest_timestamp is None:
                # No existing data - collect initial dataset
                result = self._collect_initial_data(symbol)
                stats.update(result)
            else:
                # Incremental update from latest data
                result = self._collect_incremental_data(symbol, latest_timestamp)
                stats.update(result)

            return stats

        except Exception as e:
            self.logger.error(f"Error collecting data for {symbol}: {e}")
            raise

    def _collect_initial_data(self, symbol: str) -> Dict[str, int]:
        """Collect initial historical data day by day - FIXED"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=self.days_back)

            stats = {"inserted": 0, "skipped": 0, "api_requests": 0}
            current_date = start_date

            self.logger.info(
                f"Collecting initial data for {symbol} from {start_date.date()} to {end_date.date()}"
            )

            while current_date < end_date:
                try:
                    day_end = min(current_date + timedelta(days=1), end_date)

                    # Get data for this day
                    day_data = self._fetch_coinbase_data(symbol, current_date, day_end)
                    stats["api_requests"] += 1

                    if day_data:
                        # Pre-filter for existing data before attempting to store
                        filtered_data = self._filter_existing_data(symbol, day_data)

                        if filtered_data:
                            # Store data using repository
                            inserted = self._store_historical_data(
                                symbol, filtered_data
                            )
                            stats["inserted"] += inserted
                            stats["skipped"] += len(day_data) - len(filtered_data)
                        else:
                            stats["skipped"] += len(day_data)
                            self.logger.debug(
                                f"{symbol}: {current_date.date()} - all records already exist"
                            )

                        self.logger.debug(
                            f"{symbol}: {current_date.date()} - {len(filtered_data)} new/{len(day_data)} total"
                        )

                    # Rate limiting
                    time.sleep(self.request_delay)
                    current_date = day_end

                except Exception as e:
                    self.logger.warning(
                        f"Error collecting {symbol} data for {current_date.date()}: {e}"
                    )
                    current_date += timedelta(days=1)
                    continue

            return stats

        except Exception as e:
            self.logger.error(f"Initial data collection failed for {symbol}: {e}")
            raise

    def _collect_incremental_data(
        self, symbol: str, latest_timestamp: datetime
    ) -> Dict[str, int]:
        """Collect incremental data from the latest timestamp - FIXED"""
        try:
            # Start from buffer days before latest to ensure no gaps
            start_time = latest_timestamp - timedelta(days=self.buffer_days)
            end_time = datetime.utcnow()

            stats = {"inserted": 0, "skipped": 0, "api_requests": 0}
            gap_days = (end_time - start_time).days

            self.logger.info(
                f"Collecting incremental data for {symbol} from {start_time} to {end_time} ({gap_days} days)"
            )

            if gap_days <= 7:
                # Small gap - single request
                data = self._fetch_coinbase_data(symbol, start_time, end_time)
                stats["api_requests"] += 1

                if data:
                    # Pre-filter existing data
                    filtered_data = self._filter_existing_data(symbol, data)

                    if filtered_data:
                        inserted = self._store_historical_data(symbol, filtered_data)
                        stats["inserted"] = inserted
                        stats["skipped"] = len(data) - len(filtered_data)
                    else:
                        stats["skipped"] = len(data)

            else:
                # Large gap - day by day
                result = self._collect_gap_data_day_by_day(symbol, start_time, end_time)
                stats.update(result)

            return stats

        except Exception as e:
            self.logger.error(f"Incremental data collection failed for {symbol}: {e}")
            raise

    def _collect_gap_data_day_by_day(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> Dict[str, int]:
        """Collect data day by day for large gaps - FIXED"""
        stats = {"inserted": 0, "skipped": 0, "api_requests": 0}
        current_time = start_time

        self.logger.info(
            f"Collecting gap data for {symbol} from {start_time.date()} to {end_time.date()}"
        )

        while current_time < end_time:
            try:
                day_end = min(current_time + timedelta(days=1), end_time)

                data = self._fetch_coinbase_data(symbol, current_time, day_end)
                stats["api_requests"] += 1

                if data:
                    # Pre-filter existing data
                    filtered_data = self._filter_existing_data(symbol, data)

                    if filtered_data:
                        inserted = self._store_historical_data(symbol, filtered_data)
                        stats["inserted"] += inserted
                        stats["skipped"] += len(data) - len(filtered_data)
                    else:
                        stats["skipped"] += len(data)

                time.sleep(self.request_delay)
                current_time = day_end

            except Exception as e:
                self.logger.warning(
                    f"Error collecting gap data for {symbol} on {current_time.date()}: {e}"
                )
                current_time += timedelta(days=1)
                continue

        return stats

    def _filter_existing_data(
        self, symbol: str, data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Pre-filter data to remove records that already exist - NEW METHOD
        This reduces database load by checking for existing records before attempting bulk insert
        """
        if not data:
            return []

        try:
            with self.db_manager.get_session() as session:
                # Get existing timestamps for this symbol/interval in the data range
                timestamps = [record["timestamp"] for record in data]
                min_time = min(timestamps)
                max_time = max(timestamps)

                existing_records = (
                    session.query(Historical.timestamp)
                    .filter(
                        and_(
                            Historical.symbol == symbol,
                            Historical.interval_minutes == self.interval_minutes,
                            Historical.timestamp >= min_time,
                            Historical.timestamp <= max_time,
                        )
                    )
                    .all()
                )

                # Create set of existing timestamps for fast lookup
                existing_timestamps = {record.timestamp for record in existing_records}

                # Filter out existing records
                new_data = []
                for record in data:
                    if record["timestamp"] not in existing_timestamps:
                        new_data.append(record)

                self.logger.debug(
                    f"Filtered {symbol}: {len(new_data)} new/{len(data)} total records"
                )

                return new_data

        except Exception as e:
            self.logger.warning(f"Error pre-filtering data for {symbol}: {e}")
            # If pre-filtering fails, return all data and let repository handle duplicates
            return data

    def _fetch_coinbase_data(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch historical data from Coinbase API - ENHANCED"""
        try:
            # Convert interval to Coinbase granularity (seconds)
            granularity = self._get_coinbase_granularity()

            # Format timestamps for Coinbase API
            start_iso = start_time.isoformat()
            end_iso = end_time.isoformat()

            # Coinbase API endpoint
            url = f"{self.coinbase_base_url}/products/{symbol}/candles"
            params = {"start": start_iso, "end": end_iso, "granularity": granularity}

            self.logger.debug(
                f"Fetching {symbol} data: {start_time.date()} to {end_time.date()}"
            )

            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 429:
                # Rate limited - increase delay
                self.request_delay = min(self.request_delay * 2, self.max_request_delay)
                self.logger.warning(
                    f"Rate limited, increasing delay to {self.request_delay}s"
                )
                time.sleep(self.request_delay)
                # Retry once
                response = requests.get(url, params=params, timeout=30)

            response.raise_for_status()
            candles = response.json()

            if not candles:
                self.logger.debug(f"No data returned for {symbol}")
                return []

            # Convert Coinbase format to our format with validation
            processed_data = []
            for candle in candles:
                try:
                    # Coinbase format: [timestamp, low, high, open, close, volume]
                    timestamp, low, high, open_price, close, volume = candle

                    # Validate data integrity
                    if not all(
                        isinstance(x, (int, float))
                        for x in [low, high, open_price, close]
                    ):
                        self.logger.debug(f"Skipping invalid candle data: {candle}")
                        continue

                    # Validate OHLC logic
                    if not (low <= open_price <= high and low <= close <= high):
                        self.logger.debug(f"Skipping invalid OHLC data: {candle}")
                        continue

                    processed_data.append(
                        {
                            "symbol": symbol,
                            "timestamp": datetime.fromtimestamp(timestamp),
                            "interval_minutes": self.interval_minutes,
                            "open": float(open_price),
                            "high": float(high),
                            "low": float(low),
                            "close": float(close),
                            "volume": float(volume) if volume else 0.0,
                        }
                    )

                except (ValueError, TypeError, IndexError) as e:
                    self.logger.debug(
                        f"Skipping malformed candle: {candle}, error: {e}"
                    )
                    continue

            # Sort by timestamp (oldest first)
            processed_data.sort(key=lambda x: x["timestamp"])

            self.logger.debug(
                f"Processed {len(processed_data)} valid records for {symbol}"
            )
            return processed_data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed for {symbol}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Data processing failed for {symbol}: {e}")
            raise

    def _get_coinbase_granularity(self) -> int:
        """Convert interval minutes to Coinbase granularity (seconds)"""
        # Coinbase supported granularities
        if self.interval_minutes <= 5:
            return 300  # 5 minutes
        elif self.interval_minutes <= 15:
            return 900  # 15 minutes
        elif self.interval_minutes <= 60:
            return 3600  # 1 hour
        else:
            return 86400  # 1 day

    def _store_historical_data(self, symbol: str, data: List[Dict[str, Any]]) -> int:
        """
        Store historical data using repository - ENHANCED
        This method now relies on the repository's improved duplicate handling
        """
        if not data:
            return 0

        try:
            # Use repository's enhanced bulk insert method
            inserted_count = self.historical_repo.bulk_insert(data)
            return inserted_count

        except Exception as e:
            self.logger.error(f"Error storing historical data for {symbol}: {e}")
            # Don't re-raise - log error and return 0 to continue with other symbols
            return 0

    def validate_collected_data(self, symbol: str, data: List[Dict[str, Any]]) -> bool:
        """
        Validate collected data before storage - NEW METHOD
        Performs comprehensive validation to ensure data quality
        """
        if not data:
            return True  # Empty data is valid (no data to collect)

        try:
            for i, record in enumerate(data):
                # Check required fields
                required_fields = [
                    "symbol",
                    "timestamp",
                    "interval_minutes",
                    "open",
                    "high",
                    "low",
                    "close",
                ]
                missing_fields = [
                    field for field in required_fields if field not in record
                ]

                if missing_fields:
                    self.logger.warning(f"Record {i} missing fields: {missing_fields}")
                    return False

                # Validate OHLC relationships
                open_price, high, low, close = (
                    record["open"],
                    record["high"],
                    record["low"],
                    record["close"],
                )

                if not (low <= open_price <= high and low <= close <= high):
                    self.logger.warning(
                        f"Record {i} has invalid OHLC: O={open_price}, H={high}, L={low}, C={close}"
                    )
                    return False

                # Check for reasonable values (not negative, not zero for most cases)
                if any(val <= 0 for val in [open_price, high, low, close]):
                    self.logger.warning(f"Record {i} has non-positive price values")
                    return False

                # Validate timestamp
                if not isinstance(record["timestamp"], datetime):
                    self.logger.warning(f"Record {i} has invalid timestamp type")
                    return False

            # Check for chronological order
            timestamps = [record["timestamp"] for record in data]
            if timestamps != sorted(timestamps):
                self.logger.warning("Data is not in chronological order")

                # Sort the data
                data.sort(key=lambda x: x["timestamp"])
                self.logger.info("Data sorted chronologically")

            self.logger.debug(f"Validated {len(data)} records for {symbol}")
            return True

        except Exception as e:
            self.logger.error(f"Data validation failed for {symbol}: {e}")
            return False

    def check_data_integrity_post_collection(self, symbol: str) -> Dict[str, Any]:
        """
        Check data integrity after collection - NEW METHOD
        Provides detailed statistics about the collected data
        """
        try:
            integrity_report = self.historical_repo.check_data_integrity(
                symbol, self.interval_minutes
            )

            # Add collector-specific checks
            gaps = self.historical_repo.get_data_gaps(
                symbol, self.interval_minutes, self.interval_minutes
            )
            integrity_report["data_gaps"] = len(gaps)
            integrity_report["gap_details"] = gaps[:5]  # First 5 gaps for analysis

            return integrity_report

        except Exception as e:
            self.logger.error(f"Integrity check failed for {symbol}: {e}")
            return {"error": str(e)}

    def get_collection_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive collection summary - NEW METHOD
        Provides overview of all collected data across symbols
        """
        try:
            symbols = self._get_monitored_symbols()
            summary = {
                "collector_type": self.get_collector_name(),
                "interval_minutes": self.interval_minutes,
                "monitored_symbols": len(symbols),
                "symbol_details": {},
            }

            for symbol in symbols:
                try:
                    symbol_summary = self.historical_repo.get_record_count_by_symbol(
                        symbol
                    )
                    integrity = self.check_data_integrity_post_collection(symbol)

                    summary["symbol_details"][symbol] = {
                        "record_counts": symbol_summary,
                        "integrity": integrity,
                    }

                except Exception as e:
                    summary["symbol_details"][symbol] = {"error": str(e)}

            return summary

        except Exception as e:
            self.logger.error(f"Error generating collection summary: {e}")
            return {"error": str(e)}
