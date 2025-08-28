# collectors/account_collector.py
"""
Refactored account collector using repository pattern
"""

from typing import Dict, Any
from datetime import datetime

from .base_collector import BaseCollector
from database.connections import DatabaseManager
from database.models import Account
from utils.retry import RetryConfig
from robinhood import RobinhoodCryptoAPI

from utils.logger import get_logger
logger = get_logger(__name__)  

class AccountCollector(BaseCollector):
    """Refactored account collector using repository pattern"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        retry_config: RetryConfig,
        api_client: RobinhoodCryptoAPI,
    ):
        super().__init__(db_manager, retry_config)
        self.api_client = api_client

    def get_collector_name(self) -> str:
        return "Account Information"

    def collect_and_store(self) -> bool:
        """Collect account data using repository pattern"""
        try:
            # Get account information
            account_data = self.api_client.get_account()
            if not self.validate_data(account_data):
                return False

            # Process account data
            processed_account = {
                "account_number": account_data.get("account_number", ""),
                "status": account_data.get("status", ""),
                "buying_power": float(account_data.get("buying_power", 0.0)),
                "currency": account_data.get("buying_power_currency", "USD"),
            }

            if not processed_account["account_number"]:
                self.logger.error("Account number is missing from API response")
                return False

            # Store using repository pattern
            from database import DatabaseSession

            with DatabaseSession(self.db_manager) as db_session:
                # Check if account exists
                existing_account = (
                    db_session.query(Account)
                    .filter_by(account_number=processed_account["account_number"])
                    .first()
                )

                if existing_account:
                    # Update existing account
                    for key, value in processed_account.items():
                        if hasattr(existing_account, key):
                            setattr(existing_account, key, value)
                    existing_account.updated_at = datetime.utcnow()
                    action = "updated"
                else:
                    # Create new account
                    new_account = Account(**processed_account)
                    db_session.add(new_account)
                    action = "created"

            # Log statistics
            self.log_collection_stats(
                {
                    "Account": f"{action} - {processed_account['account_number']}",
                    "Status": processed_account["status"],
                    "Buying Power": f"${processed_account['buying_power']:,.2f}",
                }
            )

            return True

        except Exception as e:
            self.logger.error(f"Error in account collection: {e}")
            return False
