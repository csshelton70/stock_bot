# collectors/crypto_collector.py
"""
Refactored crypto collector using repository pattern
"""
from typing import List, Dict, Any
from datetime import datetime

from .base_collector import BaseCollector
from data.connections.database_session import DatabaseManager
from data import Crypto
from data.repositories.crypto_repository import CryptoRepository
from utils.retry import RetryConfig
from robinhood import RobinhoodCryptoAPI

from utils.logger import get_logger

logger = get_logger(__name__)


class CryptoCollector(BaseCollector):
    """Fixed crypto collector using repository pattern"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        retry_config: RetryConfig,
        crypto_repo: CryptoRepository,
        api_client: RobinhoodCryptoAPI,
    ):
        super().__init__(db_manager, retry_config)
        self.crypto_repo = crypto_repo
        self.api_client = api_client

    def get_collector_name(self) -> str:
        return "Cryptocurrency Market Data"

    def collect_and_store(self) -> bool:
        """Collect crypto data using repository pattern"""
        try:
            # Fetch all trading pairs from API
            trading_pairs_response = (
                self.api_client.get_trading_pairs()
            )  # Get all pairs
            trading_pairs = trading_pairs_response.get("results", [])

            if not self.validate_data(trading_pairs):
                return False

            # Extract symbols for price lookup
            symbols = [
                pair.get("symbol") for pair in trading_pairs if pair.get("symbol")
            ]

            if not symbols:
                self.logger.error("No valid symbols found in trading pairs")
                return False

            # Get prices for all symbols in one call (pass as list, not individual calls)
            prices_response = self.api_client.get_best_bid_ask(
                symbols
            )  # Fixed: pass list directly
            prices_data = prices_response.get("results", [])

            # Create lookup dict for prices
            price_lookup = {}
            for price_data in prices_data:
                symbol = price_data.get("symbol")
                if symbol:
                    price_lookup[symbol] = price_data

            # Process trading pairs data with prices
            crypto_data = []
            for pair in trading_pairs:
                symbol = pair.get("symbol", "")
                if not symbol:
                    continue

                # Get price data for this symbol
                price_data = price_lookup.get(symbol, {})

                crypto_record = {
                    "symbol": symbol,
                    "minimum_order": float(pair.get("min_order_size", 0)),
                    "maximum_order": (
                        float(pair.get("max_order_size", 0))
                        if pair.get("max_order_size")
                        else None
                    ),
                    "monitored": False,  # Default to not monitored
                }

                # Add price data if available
                if price_data:
                    crypto_record.update(
                        {
                            "bid": float(
                                price_data.get("bid_inclusive_of_sell_spread", 0)
                            ),
                            "ask": float(
                                price_data.get("ask_inclusive_of_buy_spread", 0)
                            ),
                            "mid": float(price_data.get("price", 0)),
                        }
                    )

                crypto_data.append(crypto_record)

            # Store data using repository
            stored_count = self.crypto_repo.upsert_crypto_data(crypto_data)

            # Log statistics
            self.log_collection_stats(
                {
                    "Trading pairs processed": len(crypto_data),
                    "Records stored/updated": stored_count,
                    "Symbols with prices": len(price_lookup),
                }
            )

            return True

        except Exception as e:
            self.logger.error(f"Error in crypto collection: {e}")
            return False
