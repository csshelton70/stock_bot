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
        self, symbols: Optional[Union[str, Sequence[str]]] = None
    ) -> Dict[str, Any]:
        """
        Get available trading pairs information.

        Retrieves information about available trading pairs, including
        minimum and maximum order sizes, trading status, and other
        pair-specific configuration.

        Args:
            symbols: Optional symbol or sequence of trading pair symbols.
                    Can be a single string "BTC-USD" or list ["BTC-USD", "ETH-USD"].
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
            >>> # Single symbol (now works correctly)
            >>> pairs = client.get_trading_pairs("BTC-USD")
            >>> # Multiple symbols
            >>> pairs = client.get_trading_pairs(["BTC-USD", "ETH-USD"])
            >>> for pair in pairs['results']:
            ...     print(f"{pair['symbol']}: Min={pair['min_order_size']}")
        """
        query_params = ""
        if symbols:
            # FIX: Handle both string and list inputs correctly
            if isinstance(symbols, str):
                # Single symbol passed as string
                symbol_list = [symbols]
            else:
                # Multiple symbols passed as list/sequence
                symbol_list = list(symbols)

            symbol_params = [f"symbol={symbol.upper()}" for symbol in symbol_list]
            query_params = "?" + "&".join(symbol_params)

        path = f"/api/v1/crypto/trading/trading_pairs/{query_params}"
        return self.make_request("GET", path)

    def get_best_bid_ask(
        self, symbols: Optional[Union[str, Sequence[str]]] = None
    ) -> Dict[str, Any]:
        """
        Get best bid and ask prices for trading pairs with individual symbol error handling.

        Retrieves the current best bid and ask prices for the specified
        trading pairs. If a 400 error occurs for the batch request, this method
        will automatically retry each symbol individually to handle cases where
        some symbols are invalid or unavailable.

        Args:
            symbols: Optional symbol or sequence of trading pair symbols.
                    Can be a single string "BTC-USD" or list ["BTC-USD", "ETH-USD"].
                    If None, returns prices for all supported symbols.

        Returns:
            Dict[str, Any]: Best bid/ask prices containing:
                - results: List of price objects with bid_price and ask_price
                - failed_symbols: List of symbols that couldn't be processed (if any)

        Raises:
            RobinhoodAPIError: If the request fails for reasons other than invalid symbols

        Example:
            >>> client = MarketDataClient()
            >>> # Single symbol
            >>> prices = client.get_best_bid_ask("BTC-USD")
            >>> # Multiple symbols (some may fail individually)
            >>> prices = client.get_best_bid_ask(["BTC-USD", "ETH-USD", "INVALID-SYMBOL"])
            >>> # Check results and failed symbols
            >>> print(f"Got prices for {len(prices['results'])} symbols")
            >>> if 'failed_symbols' in prices:
            >>>     print(f"Failed symbols: {prices['failed_symbols']}")
        """
        from .robinhood_error import RobinhoodValidationError
        
        # Handle input normalization
        if symbols is None:
            # Get all symbols - make request without symbol filter
            path = "/api/v1/crypto/marketdata/best_bid_ask/"
            return self.make_request("GET", path)
        
        # Normalize symbols to list
        if isinstance(symbols, str):
            symbol_list = [symbols]
        else:
            symbol_list = list(symbols)
        
        if not symbol_list:
            return {"results": [], "failed_symbols": []}
        
        # Try batch request first (more efficient)
        try:
            symbol_params = [f"symbol={symbol.upper()}" for symbol in symbol_list]
            query_params = "?" + "&".join(symbol_params)
            path = f"/api/v1/crypto/marketdata/best_bid_ask/{query_params}"
            
            response = self.make_request("GET", path)
            # If batch request succeeds, return as-is
            return response
            
        except RobinhoodValidationError as e:
            # 400 error - likely one or more invalid symbols
            self.logger.warning(
                f"Batch request failed with validation error (status: {e.status_code}), "
                f"retrying {len(symbol_list)} symbols individually: {e}",
                exc_info=False
            )
            
            # Fall through to individual symbol processing
            
        except Exception as e:
            # Other errors should still be raised
            self.logger.error(f"Batch request failed with unexpected error: {e}", exc_info=True)
            raise
        
        # Process symbols individually
        self.logger.info(f"Processing {len(symbol_list)} symbols individually for best bid/ask")
        
        successful_results = []
        failed_symbols = []
        
        for symbol in symbol_list:
            try:
                symbol_upper = symbol.upper()
                path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol_upper}"
                
                self.logger.debug(f"Getting best bid/ask for individual symbol: {symbol_upper}")
                response = self.make_request("GET", path)
                
                # Add results from this symbol
                symbol_results = response.get("results", [])
                if symbol_results:
                    successful_results.extend(symbol_results)
                    self.logger.debug(f"Successfully got bid/ask for {symbol_upper}")
                else:
                    self.logger.warning(f"No price data returned for symbol: {symbol_upper}")
                    failed_symbols.append(symbol)
                    
            except RobinhoodValidationError as e:
                # 400 error for this specific symbol - log warning and continue
                self.logger.warning(
                    f"Symbol not found or invalid: {symbol} (status: {e.status_code}) - {e.message}",
                    exc_info=False
                )
                failed_symbols.append(symbol)
                continue
                
            except Exception as e:
                # Other errors for individual symbols
                self.logger.error(f"Failed to get bid/ask for {symbol}: {e}", exc_info=True)
                failed_symbols.append(symbol)
                continue
        
        # Prepare response
        response_data = {"results": successful_results}
        
        if failed_symbols:
            response_data["failed_symbols"] = failed_symbols
            self.logger.warning(
                f"Completed bid/ask request: {len(successful_results)} successful, "
                f"{len(failed_symbols)} failed symbols: {failed_symbols}"
            )
        else:
            self.logger.info(f"Successfully got bid/ask for all {len(successful_results)} symbols")
        
        return response_data


    # Additional helper method for safer symbol validation
    def get_best_bid_ask_safe(
        self, symbols: Optional[Union[str, Sequence[str]]] = None, 
        validate_symbols: bool = True
    ) -> Dict[str, Any]:
        """
        Get best bid and ask prices with optional symbol validation.
        
        This is a safer wrapper around get_best_bid_ask that can optionally
        validate symbols before making the request.
        
        Args:
            symbols: Symbol or sequence of symbols
            validate_symbols: If True, validates symbols using get_trading_pairs first
            
        Returns:
            Dict[str, Any]: Best bid/ask prices with validation info
            
        Example:
            >>> # Validate symbols first, then get prices
            >>> prices = client.get_best_bid_ask_safe(["BTC-USD", "FAKE-USD"], validate_symbols=True)
            >>> print(f"Valid symbols: {prices.get('validated_symbols', [])}")
            >>> print(f"Invalid symbols: {prices.get('invalid_symbols', [])}")
        """
        if symbols is None or not validate_symbols:
            return self.get_best_bid_ask(symbols)
        
        # Normalize to list
        if isinstance(symbols, str):
            symbol_list = [symbols]
        else:
            symbol_list = list(symbols)
        
        self.logger.debug(f"Validating {len(symbol_list)} symbols before getting bid/ask")
        
        # Validate symbols first by checking trading pairs
        try:
            trading_pairs_response = self.get_trading_pairs(symbol_list)
            valid_trading_pairs = trading_pairs_response.get("results", [])
            valid_symbols = [pair["symbol"] for pair in valid_trading_pairs]
            invalid_symbols = [sym for sym in symbol_list if sym.upper() not in [vs.upper() for vs in valid_symbols]]
            
            if invalid_symbols:
                self.logger.warning(f"Invalid symbols detected during validation: {invalid_symbols}")
            
            if valid_symbols:
                # Get prices for valid symbols only
                prices_response = self.get_best_bid_ask(valid_symbols)
                prices_response["validated_symbols"] = valid_symbols
                prices_response["invalid_symbols"] = invalid_symbols
                return prices_response
            else:
                self.logger.warning("No valid symbols found after validation")
                return {
                    "results": [], 
                    "validated_symbols": [], 
                    "invalid_symbols": invalid_symbols
                }
                
        except Exception as e:
            self.logger.warning(f"Symbol validation failed, proceeding with original request: {e}")
            # Fallback to original method if validation fails
            return self.get_best_bid_ask(symbol_list)


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
