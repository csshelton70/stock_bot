"""
Robinhood Crypto API Holdings Management Module
===============================================

This module provides holdings-related functionality for the Robinhood Crypto API.
It includes methods for retrieving and managing cryptocurrency holdings.

Classes:
    HoldingsClient: Client for holdings management operations

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

from typing import Any, Dict, List, Optional, Sequence

from .robinhood_base import RobinhoodBaseClient

# pylint:disable=line-too-long


class HoldingsClient(RobinhoodBaseClient):
    """
    Client for Robinhood Crypto holdings management operations.

    This class provides methods for retrieving cryptocurrency holdings,
    checking balances, and analyzing portfolio composition.
    """

    def get_holdings(
        self, asset_codes: Optional[Sequence[str]] = None
    ) -> Dict[str, Any]:
        """
        Get cryptocurrency holdings for the account.

        Retrieves current cryptocurrency holdings including quantities,
        asset codes, and other holding-related information.

        Args:
            asset_codes: Optional sequence of asset codes (e.g., ["BTC", "ETH"]).
                        If None, returns all holdings.

        Returns:
            Dict[str, Any]: Holdings information containing:
                - results: List of holding objects
                - next: URL for next page (if paginated)
                - previous: URL for previous page (if paginated)

        Raises:
            RobinhoodAPIError: If the request fails

        Example:
            >>> client = HoldingsClient()
            >>> holdings = client.get_holdings(["BTC", "ETH"])
            >>> for holding in holdings['results']:
            ...     if float(holding['quantity']) > 0:
            ...         print(f"{holding['asset_code']}: {holding['quantity']}")
        """
        query_params = ""
        if asset_codes:
            asset_params = [f"asset_code={code.upper()}" for code in asset_codes]
            query_params = "?" + "&".join(asset_params)

        path = f"/api/v1/crypto/trading/holdings/{query_params}"
        return self.make_request("GET", path)

    def get_all_holdings_paginated(
        self, asset_codes: Optional[Sequence[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all holdings using pagination to retrieve complete data.

        Args:
            asset_codes: Optional sequence of asset codes to filter by

        Returns:
            List[Dict[str, Any]]: All holdings across all pages

        Raises:
            RobinhoodAPIError: If any request fails

        Example:
            >>> client = HoldingsClient()
            >>> all_holdings = client.get_all_holdings_paginated()
            >>> active_holdings = [h for h in all_holdings if float(h['quantity']) > 0]
            >>> print(f"You have {len(active_holdings)} different cryptocurrencies")
        """
        all_holdings = []
        cursor = None

        while True:
            params = []
            if asset_codes:
                params.extend([f"asset_code={code.upper()}" for code in asset_codes])
            if cursor:
                params.append(f"cursor={cursor}")

            query_params = "?" + "&".join(params) if params else ""
            path = f"/api/v1/crypto/trading/holdings/{query_params}"

            response = self.make_request("GET", path)
            all_holdings.extend(response.get("results", []))

            next_url = response.get("next")
            if not next_url:
                break

            # Extract cursor from next URL
            if "cursor=" in next_url:
                cursor = next_url.split("cursor=")[1].split("&")[0]
            else:
                break

        return all_holdings

    def get_active_holdings(self) -> List[Dict[str, Any]]:
        """
        Get only holdings with non-zero quantities.

        Returns:
            List[Dict[str, Any]]: Holdings with quantity > 0

        Raises:
            RobinhoodAPIError: If the request fails
        """
        all_holdings = self.get_all_holdings_paginated()
        return [
            holding
            for holding in all_holdings
            if float(holding.get("total_quantity", 0)) > 0
        ]

    def get_holding_by_asset(self, asset_code: str) -> Optional[Dict[str, Any]]:
        """
        Get holding information for a specific asset.

        Args:
            asset_code: Asset code (e.g., "BTC", "ETH")

        Returns:
            Optional[Dict[str, Any]]: Holding information or None if not found

        Raises:
            RobinhoodAPIError: If the request fails
        """
        holdings = self.get_holdings([asset_code.upper()])
        results = holdings.get("results", [])
        return results[0] if results else None

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the entire cryptocurrency portfolio.

        Returns:
            Dict[str, Any]: Portfolio summary containing:
                - total_assets: Number of different cryptocurrencies held
                - active_assets: Number of assets with quantity > 0
                - holdings: List of all holdings
                - active_holdings: List of holdings with quantity > 0

        Raises:
            RobinhoodAPIError: If the request fails
        """
        all_holdings = self.get_all_holdings_paginated()
        active_holdings = [
            holding
            for holding in all_holdings
            if float(holding.get("total_quantity", 0)) > 0
        ]

        return {
            "total_assets": len(all_holdings),
            "active_assets": len(active_holdings),
            "holdings": all_holdings,
            "active_holdings": active_holdings,
            "asset_codes": [h["asset_code"] for h in active_holdings],
        }

    def get_balance(self, asset_code: str) -> float:
        """
        Get the current balance for a specific cryptocurrency.

        Args:
            asset_code: Asset code (e.g., "BTC", "ETH")

        Returns:
            float: Current balance (quantity) of the asset

        Raises:
            RobinhoodAPIError: If the request fails
        """
        holding = self.get_holding_by_asset(asset_code)
        if holding is None:
            return 0.0
        return float(holding.get("total_quantity", 0))

    def has_asset(self, asset_code: str, minimum_quantity: float = 0.0) -> bool:
        """
        Check if the account holds a specific asset above a minimum quantity.

        Args:
            asset_code: Asset code to check
            minimum_quantity: Minimum quantity required (default: 0.0)

        Returns:
            bool: True if holding quantity is above minimum

        Raises:
            RobinhoodAPIError: If the request fails
        """
        balance = self.get_balance(asset_code)
        return balance > minimum_quantity

    def get_nonzero_holdings(self) -> Dict[str, float]:
        """
        Get a simple mapping of asset codes to quantities for non-zero holdings.

        Returns:
            Dict[str, float]: Mapping of asset code to quantity

        Raises:
            RobinhoodAPIError: If the request fails

        Example:
            >>> client = HoldingsClient()
            >>> balances = client.get_nonzero_holdings()
            >>> for asset, quantity in balances.items():
            ...     print(f"{asset}: {quantity}")
        """
        active_holdings = self.get_active_holdings()
        return {
            holding["asset_code"]: float(holding["total_quantity"])
            for holding in active_holdings
        }

    def get_holdings_by_value_threshold(
        self, min_value_usd: float = 1.0
    ) -> List[Dict[str, Any]]:  # pylint:disable=unused-argument
        """
        Get holdings that have a minimum USD value (requires price data).

        Note: This method only returns the holdings data. To calculate USD values,
        you would need to combine this with price data from MarketDataClient.

        Args:
            min_value_usd: Minimum USD value threshold

        Returns:
            List[Dict[str, Any]]: Holdings above the threshold

        Raises:
            RobinhoodAPIError: If the request fails
        """
        # This is a placeholder implementation that returns active holdings
        # In a real implementation, you'd combine with price data
        return self.get_active_holdings()
