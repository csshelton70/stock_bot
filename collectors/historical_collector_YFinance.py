# """
# Historical data collector for Robinhood Crypto Trading App
# """

# # pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring


# import logging
# from typing import List, Dict, Any, Optional
# from datetime import datetime, timedelta
# import yfinance as yf
# from utils.retry import retry_with_backoff
# from database import DatabaseOperations
# from database import DatabaseSession
# from database import Holdings

# logger = logging.getLogger("robinhood_crypto_app.collectors.historical")


# class HistoricalCollector:
#     """Collects historical price data from Yahoo Finance"""

#     def __init__(
#         self,
#         retry_config,
#         days_back: int = 60,
#         interval_minutes: int = 5,
#         buffer_days: int = 1,
#     ):
#         self.retry_config = retry_config
#         self.days_back = days_back
#         self.interval_minutes = interval_minutes
#         self.buffer_days = buffer_days

#     def _get_holdings_symbols(self, db_session) -> List[str]:
#         """Get list of symbols from current holdings"""
#         try:
#             holdings = (
#                 db_session.query(Holdings).filter(Holdings.total_quantity > 0).all()
#             )
#             symbols = [holding.symbol for holding in holdings]
#             logger.info(f"Found {len(symbols)} symbols in holdings: {symbols}")
#             return symbols
#         except Exception as e:
#             logger.error(f"Error getting holdings symbols: {e}")
#             return []

#     def _convert_symbol_to_yahoo_format(self, symbol: str) -> str:
#         """Convert Robinhood symbol to Yahoo Finance format"""
#         # Robinhood uses BTC-USD, Yahoo Finance uses BTC-USD for crypto
#         # This should work directly for most crypto pairs
#         return symbol

#     def _convert_interval_to_yahoo_format(self) -> str:
#         """Convert minute interval to Yahoo Finance API format"""
#         # Yahoo Finance intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
#         if self.interval_minutes <= 1:
#             return "1m"
#         elif self.interval_minutes <= 2:
#             return "2m"
#         elif self.interval_minutes <= 5:
#             return "5m"
#         elif self.interval_minutes <= 15:
#             return "15m"
#         elif self.interval_minutes <= 30:
#             return "30m"
#         elif self.interval_minutes <= 60:
#             return "1h"
#         else:
#             return "1d"

#     @retry_with_backoff(max_attempts=3, backoff_factor=2.0, initial_delay=1.0)
#     def _get_historical_data(
#         self,
#         symbol: str,
#         period: str = None,
#         start: datetime = None,
#         end: datetime = None,
#     ) -> Optional[Dict[str, Any]]:
#         """Get historical data from Yahoo Finance"""
#         try:
#             yahoo_symbol = self._convert_symbol_to_yahoo_format(symbol)
#             interval = self._convert_interval_to_yahoo_format()

#             logger.debug(
#                 f"Fetching historical data for {yahoo_symbol} with interval {interval}"
#             )

#             # Create ticker object
#             ticker = yf.Ticker(yahoo_symbol)

#             # Get historical data
#             if period:
#                 # Use period for initial data fetch
#                 hist = ticker.history(period=period, interval=interval)
#             else:
#                 # Use start/end dates for incremental updates
#                 hist = ticker.history(start=start, end=end, interval=interval)

#             if hist.empty:
#                 logger.warning(f"No historical data returned for {yahoo_symbol}")
#                 return None

#             logger.info(f"Retrieved {len(hist)} historical records for {yahoo_symbol}")

#             # Convert to list of dictionaries
#             historical_data = []
#             for timestamp, row in hist.iterrows():
#                 record = {
#                     "symbol": symbol,  # Use original Robinhood symbol format
#                     "timestamp": timestamp.to_pydatetime(),
#                     "open": float(row["Open"]),
#                     "high": float(row["High"]),
#                     "low": float(row["Low"]),
#                     "close": float(row["Close"]),
#                     "volume": (
#                         float(row["Volume"])
#                         if "Volume" in row and not row.isna()["Volume"]
#                         else 0.0
#                     ),
#                 }
#                 historical_data.append(record)

#             return {"data": historical_data, "count": len(historical_data)}

#         except Exception as e:
#             logger.error(f"Error fetching historical data for {symbol}: {e}")
#             raise

#     def _determine_fetch_strategy(self, symbol: str, db_session) -> tuple:
#         """Determine what historical data to fetch based on existing data"""
#         latest_timestamp = DatabaseOperations.get_latest_historical_timestamp(
#             db_session, symbol
#         )

#         if latest_timestamp is None:
#             # No existing data, fetch initial historical data
#             period = f"{self.days_back}d"
#             logger.info(
#                 f"No existing data for {symbol}, fetching {self.days_back} days"
#             )
#             return period, "initial", None, None
#         else:
#             # Existing data found, fetch incremental data
#             # Calculate start date with buffer
#             start_date = latest_timestamp - timedelta(days=self.buffer_days)
#             end_date = datetime.now()

#             logger.info(
#                 f"Found existing data for {symbol} until {latest_timestamp}, fetching from {start_date}"
#             )
#             return None, "incremental", start_date, end_date

#     def collect_and_store(self, db_manager) -> bool:
#         """
#         Collect historical data and store in database

#         Args:
#             db_manager: Database manager instance

#         Returns:
#             True if successful, False otherwise
#         """
#         try:
#             logger.info("Starting historical data collection")

#             # Import pandas here to avoid import error if not needed
#             try:
#                 import pandas as pd
#             except ImportError:
#                 logger.error(
#                     "pandas is required for yfinance. Install with: pip install pandas"
#                 )
#                 return False

#             with DatabaseSession(db_manager) as session:
#                 # Get symbols from holdings
#                 symbols = self._get_holdings_symbols(session)
#                 if not symbols:
#                     logger.info(
#                         "No symbols found in holdings, skipping historical data collection"
#                     )
#                     return True

#                 total_records = 0
#                 successful_symbols = 0

#                 for symbol in symbols:
#                     try:
#                         logger.info(f"Processing historical data for {symbol}")

#                         # Determine fetch strategy
#                         period, strategy, start_date, end_date = (
#                             self._determine_fetch_strategy(symbol, session)
#                         )

#                         # Get historical data
#                         if strategy == "initial":
#                             result = self._get_historical_data(symbol, period=period)
#                         else:
#                             result = self._get_historical_data(
#                                 symbol, start=start_date, end=end_date
#                             )

#                         if not result or not result.get("data"):
#                             logger.warning(f"No historical data available for {symbol}")
#                             continue

#                         # Store in database
#                         count = DatabaseOperations.insert_historical_data(
#                             session, result["data"]
#                         )
#                         total_records += count
#                         successful_symbols += 1

#                         logger.info(f"Stored {count} historical records for {symbol}")

#                     except Exception as e:
#                         logger.error(
#                             f"Failed to collect historical data for {symbol}: {e}"
#                         )
#                         continue

#                 logger.info(
#                     f"Historical data collection completed: {total_records} records for {successful_symbols} symbols"
#                 )
#                 return successful_symbols > 0

#         except Exception as e:
#             logger.error(f"Failed to collect and store historical data: {e}")
#             return False
