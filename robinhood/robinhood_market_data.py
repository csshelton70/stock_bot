"""
Robinhood Crypto API Market Data Module
=======================================

This module provides market data functionality for the Robinhood Crypto API.
It includes methods for retrieving trading pairs, prices, and market information.

Classes:
    MarketDataClient: Client for market data operations

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

from typing import Any, Dict, List, Optional, Union, Sequence

from .robinhood_base import RobinhoodBaseClient
from .robinhood_enum import EstimatedPriceSide
from .robinhood_error import RobinhoodValidationError


class MarketDataClient(RobinhoodBaseClient):
    """
    Client for Robinhood Crypto market data operations.

    This class provides methods for retrieving market data including
    trading pairs, current prices, estimated execution prices, and
    other market-related information.
    """

    def get_trading_pairs(
        self, symbols: Optional[Sequence[str]] = None
    ) -> Dict[str, Any]:
        """
        Get available trading pairs information.

        Retrieves information about available trading pairs, including
        minimum and maximum order sizes, trading status, and other
        pair-specific configuration.

        Args:
            symbols: Optional sequence of trading pair symbols (e.g., ["BTC-USD", "ETH-USD"]).
                    If None, returns all available trading pairs.

        Returns:
            Dict[str, Any]: Trading pairs information containing:
                - results: List of trading pair objects
                - next: URL for next page (if paginated)
                - previous: URL for previous page (if paginated)

        Raises:
            RobinhoodAPIError: If the request fails

        Example:
            >>> client = MarketDataClient()
            >>> pairs = client.get_trading_pairs(["BTC-USD", "ETH-USD"])
            >>> for pair in pairs['results']:
            ...     print(f"{pair['symbol']}: Min={pair['min_order_size']}")
        """
        query_params = ""
        if symbols:
            symbol_params = [f"symbol={symbol.upper()}" for symbol in symbols]
            query_params = "?" + "&".join(symbol_params)

        path = f"/api/v1/crypto/trading/trading_pairs/{query_params}"
        return self.make_request("GET", path)

    def get_best_bid_ask(
        self, symbols: Optional[Sequence[str]] = None
    ) -> Dict[str, Any]:
        """
        Get best bid and ask prices for trading pairs.

        Retrieves the current best bid and ask prices for the specified
        trading pairs. These represent the best available prices for
        immediate execution.

        Args:
            symbols: Optional sequence of trading pair symbols. If None, returns
                    prices for all supported symbols.

        Returns:
            Dict[str, Any]: Best bid/ask prices containing:
                - results: List of price objects with bid_price and ask_price

        Raises:
            RobinhoodAPIError: If the request fails

        Example:
            >>> client = MarketDataClient()
            >>> prices = client.get_best_bid_ask(["BTC-USD"])
            >>> btc_price = prices['results'][0]
            >>> print(f"BTC Bid: ${btc_price['bid_price']}")
            >>> print(f"BTC Ask: ${btc_price['ask_price']}")
        """
        query_params = ""
        if symbols:
            symbol_params = [f"symbol={symbol.upper()}" for symbol in symbols]
            query_params = "?" + "&".join(symbol_params)

        path = f"/api/v1/crypto/marketdata/best_bid_ask/{query_params}"
        return self.make_request("GET", path)

    def get_estimated_price(
        self,
        symbol: str,
        side: EstimatedPriceSide,
        quantities: Sequence[Union[str, float]],
    ) -> Dict[str, Any]:
        """
        Get estimated execution prices for different quantities.

        Retrieves estimated execution prices for various order sizes.
        This helps understand the market depth and potential price impact
        of different order sizes.

        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")
            side: Price side (bid for selling, ask for buying, both for both sides)
            quantities: Sequence of quantities to get price estimates for (max 10)

        Returns:
            Dict[str, Any]: Estimated prices containing:
                - results: List of price estimates for each quantity

        Raises:
            RobinhoodValidationError: If more than 10 quantities provided or invalid inputs
            RobinhoodAPIError: If the request fails

        Example:
            >>> from robinhood_enum import EstimatedPriceSide
            >>> client = MarketDataClient()
            >>> estimates = client.get_estimated_price(
            ...     symbol="BTC-USD",
            ...     side=EstimatedPriceSide.ASK,
            ...     quantities=[0.001, 0.01, 0.1]
            ... )
            >>> for result in estimates['results']:
            ...     qty = result['quantity']
            ...     price = result['price']
            ...     print(f"{qty} BTC ≈ ${price}")
        """
        if len(quantities) > 10:
            raise RobinhoodValidationError("Maximum 10 quantities allowed per request")

        if not symbol:
            raise RobinhoodValidationError("Symbol is required")

        if not quantities:
            raise RobinhoodValidationError("At least one quantity is required")

        quantity_str = ",".join(str(q) for q in quantities)
        path = (
            f"/api/v1/crypto/marketdata/estimated_price/"
            f"?symbol={symbol.upper()}&side={side.value}&quantity={quantity_str}"
        )
        return self.make_request("GET", path)

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific trading pair.

        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")

        Returns:
            Dict[str, Any]: Trading pair information

        Raises:
            RobinhoodAPIError: If the request fails or symbol not found
        """
        trading_pairs = self.get_trading_pairs([symbol])
        results = trading_pairs.get("results", [])

        if not results:
            raise RobinhoodValidationError(f"Trading pair '{symbol}' not found")

        return results[0]

    def get_current_price(self, symbol: str) -> Dict[str, float]:
        """
        Get current bid and ask prices for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")

        Returns:
            Dict[str, float]: Current prices with bid, ask, and mid prices

        Raises:
            RobinhoodAPIError: If the request fails
        """
        prices = self.get_best_bid_ask([symbol])
        results = prices.get("results", [])

        if not results:
            raise RobinhoodValidationError(f"Price data for '{symbol}' not available")

        price_data = results[0]

        mid = float(price_data["price"])
        bid = float(price_data["bid_inclusive_of_sell_spread"])
        ask = float(price_data["ask_inclusive_of_buy_spread"])

        return {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread": ask - bid,
            "spread_percent": ((ask - bid) / bid) * 100 if bid > 0 else 0,
        }

    def get_all_trading_pairs(self) -> List[Dict[str, Any]]:
        """
        Get all available trading pairs using pagination.

        Returns:
            List[Dict[str, Any]]: All trading pairs across all pages

        Raises:
            RobinhoodAPIError: If any request fails
        """
        all_pairs = []
        cursor = None

        while True:
            params = []
            if cursor:
                params.append(f"cursor={cursor}")

            query_params = "?" + "&".join(params) if params else ""
            path = f"/api/v1/crypto/trading/trading_pairs/{query_params}"

            response = self.make_request("GET", path)
            all_pairs.extend(response.get("results", []))

            next_url = response.get("next")
            if not next_url:
                break

            # Extract cursor from next URL
            if "cursor=" in next_url:
                cursor = next_url.split("cursor=")[1].split("&")[0]
            else:
                break

        return all_pairs

    def get_market_summary(
        self, symbols: Optional[Sequence[str]] = None
    ) -> Dict[str, Any]:
        """
        Get a market summary with prices and trading pair info.

        Args:
            symbols: Optional list of symbols. If None, gets top trading pairs.

        Returns:
            Dict[str, Any]: Market summary with prices and pair information
        """
        if symbols is None:
            # Get a few popular symbols as default
            symbols = ["BTC-USD", "ETH-USD", "ADA-USD", "DOGE-USD"]

        # Get both trading pairs and prices
        trading_pairs = self.get_trading_pairs(symbols)
        prices = self.get_best_bid_ask(symbols)

        # Combine the data
        summary = {
            "symbols": symbols,
            "trading_pairs": trading_pairs.get("results", []),
            "prices": prices.get("results", []),
            "timestamp": self._get_current_timestamp(),
        }

        return summary
