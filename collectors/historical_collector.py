"""
Historical data collector for Robinhood Crypto Trading App using Coinbase API
"""

# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring


import logging
import requests
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from utils import retry_with_backoff
from database import DatabaseOperations
from database import DatabaseSession
from database import Holdings

logger = logging.getLogger("robinhood_crypto_app.collectors.historical")


class HistoricalCollector:
    """Collects historical price data from Coinbase API"""

    def __init__(
        self,
        retry_config,
        days_back: int = 60,
        interval_minutes: int = 15,
        buffer_days: int = 1,
    ):
        self.retry_config = retry_config
        self.days_back = days_back
        self.interval_minutes = interval_minutes
        self.buffer_days = buffer_days
        self.base_url = "https://api.exchange.coinbase.com"
        self.request_delay = 0.5  # Delay between requests to avoid rate limiting

    def _get_monitored_symbols(self, db_session) -> List[str]:
        """Get list of symbols that are marked as monitored"""
        try:
            from database.models import Crypto

            monitored_cryptos = (
                db_session.query(Crypto).filter(Crypto.monitored == True).all()
            )
            symbols = [crypto.symbol for crypto in monitored_cryptos]
            logger.info(f"Found {len(symbols)} monitored symbols: {symbols}")
            return symbols
        except Exception as e:
            logger.error(f"Error getting monitored symbols: {e}")
            return []

    def _convert_symbol_to_coinbase_format(self, symbol: str) -> str:
        """Convert Robinhood symbol to Coinbase format"""
        # Robinhood uses BTC-USD, Coinbase uses BTC-USD (same format)
        # But we need to ensure it's properly formatted
        if "-" in symbol:
            return symbol.upper()
        else:
            # If somehow we get just the asset code, append USD
            return f"{symbol.upper()}-USD"

    def _convert_interval_to_coinbase_granularity(self) -> int:
        """Convert minute interval to Coinbase granularity (seconds)"""
        # Coinbase granularities: 60, 300, 900, 3600, 21600, 86400
        # (1min, 5min, 15min, 1hour, 6hour, 1day)
        if self.interval_minutes <= 1:
            return 60  # 1 minute
        elif self.interval_minutes <= 5:
            return 300  # 5 minutes
        elif self.interval_minutes <= 15:
            return 900  # 15 minutes
        elif self.interval_minutes <= 60:
            return 3600  # 1 hour
        elif self.interval_minutes <= 360:
            return 21600  # 6 hours
        else:
            return 86400  # 1 day

    def _format_datetime_for_coinbase(self, dt: datetime) -> str:
        """Format datetime for Coinbase API (ISO 8601)"""
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @retry_with_backoff(max_attempts=3, backoff_factor=2.0, initial_delay=1.0)
    def _get_single_day_data_from_coinbase(
        self, symbol: str, start: datetime, end: datetime
    ) -> Optional[List[List]]:
        """Get one day of historical data from Coinbase API"""
        try:
            coinbase_symbol = self._convert_symbol_to_coinbase_format(symbol)
            granularity = self._convert_interval_to_coinbase_granularity()

            # Format dates for Coinbase API
            start_str = self._format_datetime_for_coinbase(start)
            end_str = self._format_datetime_for_coinbase(end)

            # Coinbase API endpoint
            url = f"{self.base_url}/products/{coinbase_symbol}/candles"
            params = {"start": start_str, "end": end_str, "granularity": granularity}

            logger.debug(
                f"Fetching {coinbase_symbol} data from {start_str} to {end_str} ({self.interval_minutes}min interval)"
            )

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if not data:
                logger.debug(
                    f"No data returned for {coinbase_symbol} on {start.date()} ({self.interval_minutes}min)"
                )
                return []

            logger.debug(
                f"Retrieved {len(data)} records for {coinbase_symbol} on {start.date()} ({self.interval_minutes}min)"
            )

            # Add delay to avoid rate limiting
            time.sleep(self.request_delay)

            return data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Symbol {symbol} not found on Coinbase")
                return None
            elif e.response.status_code == 429:
                logger.warning(f"Rate limited by Coinbase API, increasing delay")
                self.request_delay = min(
                    self.request_delay * 2, 5.0
                )  # Max 5 second delay
                raise  # Let retry handler deal with it
            else:
                logger.error(f"HTTP error fetching data for {symbol}: {e}")
                raise
        except Exception as e:
            logger.error(f"Error fetching single day data for {symbol}: {e}")
            raise

    def _process_coinbase_data(
        self, symbol: str, raw_data: List[List]
    ) -> List[Dict[str, Any]]:
        """
        Process raw Coinbase API data into database format

        Coinbase returns data in format: [timestamp, low, high, open, close, volume]
        """
        processed_data = []

        for candle in raw_data:
            try:
                # Coinbase candle format: [timestamp, low, high, open, close, volume]
                timestamp = datetime.fromtimestamp(candle[0])
                low_price = float(candle[1])
                high_price = float(candle[2])
                open_price = float(candle[3])
                close_price = float(candle[4])
                volume = float(candle[5])

                historical_record = {
                    "symbol": symbol,  # Use original Robinhood symbol format
                    "timestamp": timestamp,
                    "interval_minutes": self.interval_minutes,  # NEW: Include interval
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                }

                processed_data.append(historical_record)

            except (IndexError, ValueError, TypeError) as e:
                logger.warning(f"Error processing historical record for {symbol}: {e}")
                continue

        # Sort by timestamp (Coinbase sometimes returns unsorted data)
        processed_data.sort(key=lambda x: x["timestamp"])

        return processed_data

    def _fetch_initial_data_day_by_day(
        self, symbol: str, db_session
    ) -> List[Dict[str, Any]]:
        """
        Fetch initial historical data day by day to avoid API limits

        Args:
            symbol: Trading pair symbol (must be monitored)
            db_session: Database session

        Returns:
            List of processed historical records
        """
        logger.info(
            f"Fetching initial data for monitored symbol {symbol} - {self.days_back} days, one day at a time ({self.interval_minutes}min intervals)"
        )

        all_processed_data = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.days_back)

        current_date = start_date
        day_count = 0

        while current_date < end_date:
            try:
                day_count += 1
                next_date = current_date + timedelta(days=1)

                # Don't go past the end date
                if next_date > end_date:
                    next_date = end_date

                logger.debug(
                    f"Fetching day {day_count}/{self.days_back} for {symbol}: {current_date.date()} ({self.interval_minutes}min)"
                )

                # Get one day of data
                raw_data = self._get_single_day_data_from_coinbase(
                    symbol, current_date, next_date
                )

                if raw_data is None:
                    # Symbol not found on Coinbase
                    logger.warning(f"Symbol {symbol} not available on Coinbase")
                    return []

                if raw_data:  # If we got data for this day
                    # Process the data
                    day_processed_data = self._process_coinbase_data(symbol, raw_data)
                    all_processed_data.extend(day_processed_data)

                    if day_processed_data:
                        logger.debug(
                            f"Added {len(day_processed_data)} records for {symbol} on {current_date.date()} ({self.interval_minutes}min)"
                        )

                # Move to next day
                current_date = next_date

            except Exception as e:
                logger.error(
                    f"Error fetching data for {symbol} on {current_date.date()}: {e}"
                )
                # Continue to next day instead of failing completely
                current_date = current_date + timedelta(days=1)
                continue

        logger.info(
            f"Initial fetch complete for {symbol} ({self.interval_minutes}min): {len(all_processed_data)} total records"
        )
        return all_processed_data

    def _fetch_date_range_day_by_day(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical data for a date range, day by day to avoid API limits

        Args:
            symbol: Trading pair symbol
            start_date: Start date for data collection
            end_date: End date for data collection

        Returns:
            List of processed historical records
        """
        logger.info(
            f"Fetching date range for {symbol} from {start_date.date()} to {end_date.date()}, day by day ({self.interval_minutes}min intervals)"
        )

        all_processed_data = []
        current_date = start_date
        day_count = 0
        total_days = (end_date - start_date).days + 1

        while current_date < end_date:
            try:
                day_count += 1
                next_date = current_date + timedelta(days=1)

                # Don't go past the end date
                if next_date > end_date:
                    next_date = end_date

                logger.debug(
                    f"Fetching day {day_count}/{total_days} for {symbol}: {current_date.date()} ({self.interval_minutes}min)"
                )

                # Get one day of data
                raw_data = self._get_single_day_data_from_coinbase(
                    symbol, current_date, next_date
                )

                if raw_data is None:
                    # Symbol not found on Coinbase
                    logger.warning(f"Symbol {symbol} not available on Coinbase")
                    return []

                if raw_data:  # If we got data for this day
                    # Process the data
                    day_processed_data = self._process_coinbase_data(symbol, raw_data)
                    all_processed_data.extend(day_processed_data)

                    if day_processed_data:
                        logger.debug(
                            f"Added {len(day_processed_data)} records for {symbol} on {current_date.date()} ({self.interval_minutes}min)"
                        )

                # Move to next day
                current_date = next_date

            except Exception as e:
                logger.error(
                    f"Error fetching data for {symbol} on {current_date.date()}: {e}"
                )
                # Continue to next day instead of failing completely
                current_date = current_date + timedelta(days=1)
                continue

        logger.info(
            f"Date range fetch complete for {symbol} ({self.interval_minutes}min): {len(all_processed_data)} total records"
        )
        return all_processed_data

    def _fetch_incremental_data_from_latest(
        self, symbol: str, db_session
    ) -> List[Dict[str, Any]]:
        """
        Fetch incremental data from 24 hours before the latest record to now
        This ensures we don't miss data if the app hasn't run for several days

        Args:
            symbol: Trading pair symbol (must be monitored)
            db_session: Database session

        Returns:
            List of processed historical records
        """
        # Get the latest timestamp for this symbol and interval
        latest_timestamp = DatabaseOperations.get_latest_historical_timestamp(
            db_session, symbol, self.interval_minutes
        )

        if latest_timestamp is None:
            logger.warning(
                f"No latest timestamp found for {symbol} ({self.interval_minutes}min) during incremental fetch"
            )
            return []

        # Calculate date range: 24 hours before latest record to now
        start_date = latest_timestamp - timedelta(hours=24)
        end_date = datetime.now()

        days_gap = (end_date - latest_timestamp).days
        logger.info(
            f"Fetching incremental data for monitored symbol {symbol} ({self.interval_minutes}min)"
        )
        logger.info(f"Latest record: {latest_timestamp}, Gap: {days_gap} days")
        logger.info(f"Fetching from {start_date} to {end_date} (includes 24h overlap)")

        try:
            # If gap is more than 7 days, fetch day by day to avoid API limits
            if days_gap > 7:
                logger.info(
                    f"Gap is {days_gap} days, fetching day by day to avoid API limits"
                )
                return self._fetch_date_range_day_by_day(symbol, start_date, end_date)
            else:
                # Small gap, can fetch in one request
                logger.info(f"Gap is {days_gap} days, fetching in single request")
                raw_data = self._get_single_day_data_from_coinbase(
                    symbol, start_date, end_date
                )

                if raw_data is None:
                    logger.warning(f"Symbol {symbol} not available on Coinbase")
                    return []

                if not raw_data:
                    logger.debug(
                        f"No new data available for {symbol} ({self.interval_minutes}min)"
                    )
                    return []

                # Process the data
                processed_data = self._process_coinbase_data(symbol, raw_data)

                logger.info(
                    f"Incremental fetch complete for {symbol} ({self.interval_minutes}min): {len(processed_data)} records"
                )
                return processed_data

        except Exception as e:
            logger.error(
                f"Error fetching incremental data for {symbol} ({self.interval_minutes}min): {e}"
            )
            return []

    def _validate_symbol_with_coinbase(self, symbol: str) -> bool:
        """Check if symbol exists on Coinbase before attempting to fetch data"""
        try:
            coinbase_symbol = self._convert_symbol_to_coinbase_format(symbol)
            url = f"{self.base_url}/products/{coinbase_symbol}/stats"

            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                logger.debug(f"Symbol {coinbase_symbol} validated on Coinbase")
                return True
            elif response.status_code == 404:
                logger.info(f"Symbol {coinbase_symbol} not available on Coinbase")
                return False
            else:
                # For other errors, assume it might work and let the main function handle it
                logger.warning(
                    f"Could not validate symbol {coinbase_symbol} (status {response.status_code}), will attempt anyway"
                )
                return True

        except Exception as e:
            logger.warning(
                f"Error validating symbol {symbol} with Coinbase: {e}, will attempt anyway"
            )
            return True  # Assume it might work

    def collect_and_store(self, db_manager) -> bool:
        """
        Collect historical data and store in database

        Args:
            db_manager: Database manager instance

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(
                f"Starting historical data collection from Coinbase ({self.interval_minutes}min intervals)"
            )

            with DatabaseSession(db_manager) as session:
                # Get symbols that are marked as monitored
                symbols = self._get_monitored_symbols(session)
                if not symbols:
                    logger.info(
                        "No monitored symbols found, skipping historical data collection"
                    )
                    logger.info(
                        "Use 'python set_monitored_flag.py --holdings --true' to set monitored flags"
                    )
                    return True

                total_records = 0
                successful_symbols = 0
                failed_symbols = []

                for symbol in symbols:
                    try:
                        logger.info(
                            f"Processing historical data for {symbol} ({self.interval_minutes}min)"
                        )

                        # Validate symbol exists on Coinbase and is monitored
                        if not self._validate_symbol_with_coinbase(symbol):
                            logger.warning(
                                f"Skipping {symbol} - not available on Coinbase"
                            )
                            failed_symbols.append(symbol)
                            continue

                        # Check if we have existing data for this interval
                        latest_timestamp = (
                            DatabaseOperations.get_latest_historical_timestamp(
                                session, symbol, self.interval_minutes
                            )
                        )

                        if latest_timestamp is None:
                            # Initial pull - fetch day by day
                            logger.info(
                                f"No existing data for monitored symbol {symbol} ({self.interval_minutes}min) - performing initial fetch"
                            )
                            processed_data = self._fetch_initial_data_day_by_day(
                                symbol, session
                            )
                        else:
                            # Incremental pull - fetch from 24 hours before latest record
                            logger.info(
                                f"Found existing data for monitored symbol {symbol} ({self.interval_minutes}min) until {latest_timestamp} - performing incremental fetch"
                            )
                            processed_data = self._fetch_incremental_data_from_latest(
                                symbol, session
                            )

                        if not processed_data:
                            logger.warning(
                                f"No data retrieved for {symbol} ({self.interval_minutes}min)"
                            )
                            failed_symbols.append(symbol)
                            continue

                        # Store in database (this handles duplicates automatically)
                        count = DatabaseOperations.insert_historical_data(
                            session, processed_data
                        )
                        total_records += count
                        successful_symbols += 1

                        logger.info(
                            f"Stored {count} new historical records for monitored symbol {symbol} ({self.interval_minutes}min)"
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to collect historical data for {symbol} ({self.interval_minutes}min): {e}"
                        )
                        failed_symbols.append(symbol)
                        continue

                # Log summary
                if failed_symbols:
                    logger.warning(
                        f"Failed to collect data for monitored symbols ({self.interval_minutes}min): {failed_symbols}"
                    )

                logger.info(
                    f"Historical data collection completed ({self.interval_minutes}min): {total_records} new records for {successful_symbols}/{len(symbols)} monitored symbols"
                )
                return (
                    successful_symbols > 0 or len(symbols) == 0
                )  # Success if we processed something or had nothing to process

        except Exception as e:
            logger.error(
                f"Failed to collect and store historical data ({self.interval_minutes}min): {e}"
            )
            return False
