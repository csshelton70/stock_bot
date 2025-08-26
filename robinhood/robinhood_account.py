"""
Robinhood Crypto API Account Management Module
==============================================

This module provides account-related functionality for the Robinhood Crypto API.
It includes methods for retrieving account information and managing account settings.

Classes:
    AccountClient: Client for account management operations

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

from typing import Any, Dict

from .robinhood_base import RobinhoodBaseClient


class AccountClient(RobinhoodBaseClient):
    """
    Client for Robinhood Crypto account management operations.

    This class provides methods for retrieving account information,
    checking account status, and managing account-related settings.
    """

    def get_account(self) -> Dict[str, Any]:
        """
        Get crypto trading account details.

        Retrieves comprehensive information about the user's crypto trading account,
        including account number, status, buying power, and currency information.

        Returns:
            Dict[str, Any]: Account information containing:
                - account_number (str): Unique account identifier
                - status (str): Account status (e.g., "active")
                - buying_power (str): Available buying power amount
                - buying_power_currency (str): Currency of buying power (e.g., "USD")

        Raises:
            RobinhoodAPIError: If the request fails
            RobinhoodAuthError: If authentication fails

        Example:
            >>> client = AccountClient()
            >>> account = client.get_account()
            >>> print(f"Account: {account['account_number']}")
            >>> print(f"Buying Power: ${account['buying_power']}")
        """
        return self.make_request("GET", "/api/v1/crypto/trading/accounts/")

    def get_account_status(self) -> str:
        """
        Get the current account status.

        Returns:
            str: Account status (e.g., "active", "restricted", "closed")

        Raises:
            RobinhoodAPIError: If the request fails
        """
        account = self.get_account()
        return account.get("status", "unknown")

    def get_buying_power(self) -> Dict[str, str]:
        """
        Get current buying power information.

        Returns:
            Dict[str, str]: Buying power information containing:
                - amount (str): Available buying power amount
                - currency (str): Currency of the buying power

        Raises:
            RobinhoodAPIError: If the request fails
        """
        account = self.get_account()
        return {
            "amount": account.get("buying_power", "0"),
            "currency": account.get("buying_power_currency", "USD"),
        }

    def is_account_active(self) -> bool:
        """
        Check if the account is in active status.

        Returns:
            bool: True if account status is "active"

        Raises:
            RobinhoodAPIError: If the request fails
        """
        status = self.get_account_status()
        return status.lower() == "active"
