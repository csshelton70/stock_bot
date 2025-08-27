# collectors/historical_collector.py
"""
Refactored Historical Collector using the new base collector architecture
Collects historical OHLCV candlestick data from Coinbase API
"""

import time
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

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
        """Main collection logic using repository pattern"""
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
                "symbols_with_errors": 0,
                "api_requests_made": 0,
            }

            # Process each monitored symbol
            for symbol in monitored_symbols:
                try:
                    records_added = self._collect_symbol_data(symbol)
                    collection_stats["symbols_processed"] += 1
                    collection_stats["records_inserted"] += records_added

                    self.logger.info(f"Collected {records_added} records for {symbol}")

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

    def _collect_symbol_data(self, symbol: str) -> int:
        """Collect historical data for a single symbol"""
        try:
            # Check if we have existing data
            latest_timestamp = self.historical_repo.get_latest_timestamp(
                symbol, self.interval_minutes
            )

            if latest_timestamp is None:
                # No existing data - collect initial dataset
                return self._collect_initial_data(symbol)
            else:
                # Incremental update from latest data
                return self._collect_incremental_data(symbol, latest_timestamp)

        except Exception as e:
            self.logger.error(f"Error collecting data for {symbol}: {e}")
            raise

    def _collect_initial_data(self, symbol: str) -> int:
        """Collect initial historical data day by day"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=self.days_back)

            total_records = 0
            current_date = start_date

            self.logger.info(
                f"Collecting initial data for {symbol} from {start_date.date()} to {end_date.date()}"
            )

            while current_date < end_date:
                try:
                    day_end = min(current_date + timedelta(days=1), end_date)

                    # Get data for this day
                    day_data = self._fetch_coinbase_data(symbol, current_date, day_end)

                    if day_data:
                        # Store data using repository
                        inserted = self._store_historical_data(symbol, day_data)
                        total_records += inserted

                        self.logger.debug(
                            f"{symbol}: {current_date.date()} - {inserted} records"
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

            return total_records

        except Exception as e:
            self.logger.error(f"Initial data collection failed for {symbol}: {e}")
            raise

    def _collect_incremental_data(self, symbol: str, latest_timestamp: datetime) -> int:
        """Collect incremental data from the latest timestamp"""
        try:
            # Start from buffer days before latest to ensure no gaps
            start_time = latest_timestamp - timedelta(days=self.buffer_days)
            end_time = datetime.utcnow()

            gap_days = (end_time - start_time).days

            if gap_days <= 7:
                # Small gap - single request
                data = self._fetch_coinbase_data(symbol, start_time, end_time)
                return self._store_historical_data(symbol, data) if data else 0
            else:
                # Large gap - day by day
                return self._collect_gap_data_day_by_day(symbol, start_time, end_time)

        except Exception as e:
            self.logger.error(f"Incremental data collection failed for {symbol}: {e}")
            raise

    def _collect_gap_data_day_by_day(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> int:
        """Collect data day by day for large gaps"""
        total_records = 0
        current_time = start_time

        self.logger.info(
            f"Collecting gap data for {symbol} from {start_time.date()} to {end_time.date()}"
        )

        while current_time < end_time:
            try:
                day_end = min(current_time + timedelta(days=1), end_time)

                data = self._fetch_coinbase_data(symbol, current_time, day_end)
                if data:
                    inserted = self._store_historical_data(symbol, data)
                    total_records += inserted

                time.sleep(self.request_delay)
                current_time = day_end

            except Exception as e:
                self.logger.warning(
                    f"Error collecting gap data for {symbol} on {current_time.date()}: {e}"
                )
                current_time += timedelta(days=1)
                continue

        return total_records

    def _fetch_coinbase_data(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch historical data from Coinbase API"""
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

            # Convert Coinbase format to our format
            processed_data = []
            for candle in candles:
                # Coinbase format: [timestamp, low, high, open, close, volume]
                timestamp, low, high, open_price, close, volume = candle

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

            # Sort by timestamp (oldest first)
            processed_data.sort(key=lambda x: x["timestamp"])

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
        """Store historical data using repository"""
        if not data:
            return 0

        try:
            # Use repository to bulk insert
            inserted_count = self.historical_repo.bulk_insert(data)
            return inserted_count

        except Exception as e:
            # Handle duplicate entries gracefully
            if "UNIQUE constraint failed" in str(e) or "IntegrityError" in str(e):
                # Try inserting one by one to skip duplicates
                return self._store_data_individually(data)
            else:
                self.logger.error(f"Error storing historical data: {e}")
                raise

    def _store_data_individually(self, data: List[Dict[str, Any]]) -> int:
        """Store data individually to handle duplicates"""
        inserted_count = 0

        with DatabaseSession(self.db_manager) as db_session:
            for record in data:
                try:
                    # Check if record already exists
                    existing = (
                        db_session.query(Historical)
                        .filter_by(
                            symbol=record["symbol"],
                            timestamp=record["timestamp"],
                            interval_minutes=record["interval_minutes"],
                        )
                        .first()
                    )

                    if not existing:
                        historical_record = Historical(**record)
                        db_session.add(historical_record)
                        inserted_count += 1

                except Exception as e:
                    self.logger.debug(f"Skipping duplicate record: {e}")
                    continue

        return inserted_count
