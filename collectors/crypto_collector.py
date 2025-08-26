"""
Crypto pairs and prices data collector for Robinhood Crypto Trading App
"""

# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring


import logging
from typing import List, Dict, Any
from robinhood import create_client
from utils import retry_with_backoff
from database import DatabaseOperations
from database import DatabaseSession

logger = logging.getLogger("robinhood_crypto_app.collectors.crypto")


class CryptoCollector:
    """Collects cryptocurrency pairs and current prices"""

    def __init__(self, retry_config, api_key: str, private_key_base64: str):
        self.retry_config = retry_config
        self.api_key = api_key
        self.private_key_base64 = private_key_base64

    @retry_with_backoff(max_attempts=3, backoff_factor=2.0, initial_delay=1.0)
    def _get_crypto_pairs_and_prices(self) -> List[Dict[str, Any]]:
        """Get cryptocurrency trading pairs and current prices from Robinhood"""
        try:
            logger.debug("Fetching crypto currency pairs and prices from Robinhood")

            with create_client(
                api_key=self.api_key, private_key_base64=self.private_key_base64
            ) as client:
                # Get trading pairs
                trading_pairs = client.get_all_trading_pairs()
                logger.info(f"Retrieved {len(trading_pairs)} trading pairs")

                # Get symbols for price quotes
                symbols = [
                    pair.get("symbol") for pair in trading_pairs if pair.get("symbol")
                ]

                # Get current prices
                prices = client.get_best_bid_ask(symbols)
                logger.info(
                    f"Retrieved prices for {len(prices.get('results', []))} symbols"
                )

                return self._process_crypto_data(trading_pairs, prices)

        except Exception as e:
            logger.error(f"Error fetching crypto pairs and prices: {e}")
            raise

    def _process_crypto_data(
        self, pairs: List[Dict], prices_response: Dict
    ) -> List[Dict[str, Any]]:
        """Process and combine crypto pairs and prices data"""
        processed_data = []

        # Create a lookup for prices by symbol
        prices_lookup = {}
        for price_data in prices_response.get("results", []):
            symbol = price_data.get("symbol")
            if symbol:
                prices_lookup[symbol] = price_data

        for pair in pairs:
            try:
                symbol = pair.get("symbol", "")
                if not symbol:
                    continue

                # Get price data for this symbol
                price_data = prices_lookup.get(symbol, {})

                # Extract bid and ask prices
                bid_price = None
                ask_price = None

                if price_data:
                    bid_price = (
                        float(price_data.get("bid_inclusive_of_sell_spread", 0))
                        if price_data.get("bid_inclusive_of_sell_spread")
                        else None
                    )
                    ask_price = (
                        float(price_data.get("ask_inclusive_of_buy_spread", 0))
                        if price_data.get("ask_inclusive_of_buy_spread")
                        else None
                    )

                # Calculate mid price
                mid_price = None
                if bid_price is not None and ask_price is not None:
                    mid_price = (bid_price + ask_price) / 2

                # Extract order limits
                min_order = None
                max_order = None

                if "min_order_size" in pair:
                    min_order = (
                        float(pair["min_order_size"])
                        if pair["min_order_size"]
                        else None
                    )

                if "max_order_size" in pair:
                    max_order = (
                        float(pair["max_order_size"])
                        if pair["max_order_size"]
                        else None
                    )

                crypto_data = {
                    "symbol": symbol,
                    "minimum_order": min_order,
                    "maximum_order": max_order,
                    "bid": bid_price,
                    "mid": mid_price,
                    "ask": ask_price,
                }

                processed_data.append(crypto_data)
                logger.debug(f"Processed crypto data for {symbol}")

            except Exception as e:
                logger.warning(
                    f"Error processing crypto pair {pair.get('symbol', 'unknown')}: {e}"
                )
                continue

        logger.info(f"Processed {len(processed_data)} crypto records")
        return processed_data

    def collect_and_store(self, db_manager) -> bool:
        """
        Collect crypto data and store in database

        Args:
            db_manager: Database manager instance

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting crypto data collection")

            # Get crypto pairs and prices
            crypto_data = self._get_crypto_pairs_and_prices()
            if not crypto_data:
                logger.warning("No crypto data collected")
                return False

            # Store in database
            with DatabaseSession(db_manager) as session:
                count = DatabaseOperations.upsert_crypto_data(session, crypto_data)
                logger.info(f"Successfully stored {count} crypto records")

            return True

        except Exception as e:
            logger.error(f"Failed to collect and store crypto data: {e}")
            return False
