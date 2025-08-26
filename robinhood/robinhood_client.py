"""
Robinhood Crypto API Unified Client Module
==========================================

This module provides a unified client that combines all API functionality
into a single, easy-to-use interface.

Classes:
    RobinhoodCryptoAPI: Unified client with all API functionality

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

# pylint:disable=broad-exception-caught

from typing import Optional

from .robinhood_config import RobinhoodConfig
from .robinhood_account import AccountClient
from .robinhood_market_data import MarketDataClient
from .robinhood_holdings import HoldingsClient
from .robinhood_orders import OrdersClient


class RobinhoodCryptoAPI(AccountClient, MarketDataClient, HoldingsClient, OrdersClient):
    """
    Unified Robinhood Crypto API client with all functionality.

    This class inherits from all the specialized client classes to provide
    a single interface for all Robinhood Crypto API operations including
    account management, market data, holdings, and order management.

    Example:
        >>> # Create unified client
        >>> with RobinhoodCryptoAPI() as client:
        ...     # Account operations
        ...     account = client.get_account()
        ...
        ...     # Market data operations
        ...     prices = client.get_best_bid_ask(["BTC-USD"])
        ...
        ...     # Holdings operations
        ...     holdings = client.get_holdings()
        ...
        ...     # Order operations
        ...     orders = client.get_orders(limit=10)
    """

    def __init__(self, config: Optional[RobinhoodConfig] = None) -> None:
        """
        Initialize the unified API client.

        Args:
            config: Configuration object. If None, loads from environment variables.

        Raises:
            RobinhoodAuthError: If API key or private key are missing
            ValueError: If configuration validation fails
        """
        # Initialize the base client (only need to do this once since all inherit from it)
        super().__init__(config)

        self.logger.info("RobinhoodCryptoAPI unified client initialized successfully")

    def get_client_info(self) -> dict:
        """
        Get information about the client and its capabilities.

        Returns:
            dict: Client information and available methods
        """
        return {
            "client_type": "RobinhoodCryptoAPI",
            "version": "1.0.0",
            "base_url": self.config.base_url,
            "capabilities": {
                "account_management": [
                    "get_account",
                    "get_account_status",
                    "get_buying_power",
                    "is_account_active",
                ],
                "market_data": [
                    "get_trading_pairs",
                    "get_best_bid_ask",
                    "get_estimated_price",
                    "get_symbol_info",
                    "get_current_price",
                    "get_all_trading_pairs",
                    "get_market_summary",
                ],
                "holdings": [
                    "get_holdings",
                    "get_all_holdings_paginated",
                    "get_active_holdings",
                    "get_holding_by_asset",
                    "get_portfolio_summary",
                    "get_balance",
                    "has_asset",
                    "get_nonzero_holdings",
                ],
                "orders": [
                    "get_orders",
                    "get_order",
                    "get_all_orders_paginated",
                    "place_market_order",
                    "place_limit_order",
                    "place_stop_loss_order",
                    "place_stop_limit_order",
                    "cancel_order",
                    "get_open_orders",
                    "get_filled_orders",
                    "cancel_all_open_orders",
                    "get_order_status",
                    "is_order_filled",
                    "is_order_open",
                ],
            },
        }

    def quick_status(self) -> dict:
        """
        Get a quick status overview of the account.

        Returns:
            dict: Quick status information
        """
        try:
            account = self.get_account()
            active_holdings = self.get_active_holdings()
            open_orders = self.get_open_orders()

            return {
                "account_status": account.get("status", "unknown"),
                "buying_power": account.get("buying_power", "0"),
                "active_assets": len(active_holdings),
                "open_orders": len(open_orders),
                "health_check": True,
            }
        except Exception as e:
            return {"error": str(e), "health_check": False}
