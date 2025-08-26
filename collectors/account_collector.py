"""
Account information data collector for Robinhood Crypto Trading App
"""

# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring


import logging
from typing import Dict, Any, Optional
from robinhood import create_client
from utils.retry import retry_with_backoff
from database import DatabaseOperations
from database import DatabaseSession

logger = logging.getLogger("robinhood_crypto_app.collectors.account")


class AccountCollector:
    """Collects account information"""

    def __init__(self, retry_config, api_key: str, private_key_base64: str):
        self.retry_config = retry_config
        self.api_key = api_key
        self.private_key_base64 = private_key_base64

    @retry_with_backoff(max_attempts=3, backoff_factor=2.0, initial_delay=1.0)
    def _get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information from Robinhood"""
        try:
            logger.debug("Fetching account information from Robinhood")

            with create_client(
                api_key=self.api_key, private_key_base64=self.private_key_base64
            ) as client:
                # Get account information
                account = client.get_account()

                if not account:
                    logger.warning("No account information returned from Robinhood")
                    return None

                account_data = {
                    "account_number": account.get("account_number", ""),
                    "status": account.get("status", "unknown"),
                    "buying_power": (
                        float(account.get("buying_power", 0))
                        if account.get("buying_power")
                        else 0.0
                    ),
                    "currency": account.get("buying_power_currency", "USD"),
                }

                logger.info("Successfully retrieved account information")
                return account_data

        except Exception as e:
            logger.error(f"Error fetching account information: {e}")
            raise

    def collect_and_store(self, db_manager) -> bool:
        """
        Collect account data and store in database

        Args:
            db_manager: Database manager instance

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting account data collection")

            # Get account information
            account_data = self._get_account_info()
            if not account_data:
                logger.warning("No account data collected")
                return False

            # Validate required fields
            if not account_data.get("account_number"):
                logger.error("Account number is missing from account data")
                return False

            # Store in database
            with DatabaseSession(db_manager) as session:
                success = DatabaseOperations.upsert_account_data(session, account_data)
                if success:
                    logger.info(
                        f"Successfully stored account data for account {account_data['account_number']}"
                    )
                else:
                    logger.error("Failed to store account data")

                return success

        except Exception as e:
            logger.error(f"Failed to collect and store account data: {e}")
            return False
