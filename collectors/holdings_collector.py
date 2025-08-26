"""
Holdings data collector for Robinhood Crypto Trading App
"""

import logging
from typing import List, Dict, Any
from robinhood import create_client
from utils.retry import retry_with_backoff
from database import DatabaseOperations
from database import DatabaseSession

logger = logging.getLogger("robinhood_crypto_app.collectors.holdings")


class HoldingsCollector:
    """Collects portfolio holdings"""

    def __init__(self, retry_config, api_key: str, private_key_base64: str):
        self.retry_config = retry_config
        self.api_key = api_key
        self.private_key_base64 = private_key_base64

    @retry_with_backoff(max_attempts=3, backoff_factor=2.0, initial_delay=1.0)
    def _get_crypto_holdings(self) -> List[Dict[str, Any]]:
        """Get crypto holdings from Robinhood using your API"""
        try:
            logger.debug("Fetching crypto holdings from Robinhood")

            with create_client(
                api_key=self.api_key, private_key_base64=self.private_key_base64
            ) as client:
                # Get all holdings using your Robinhood API
                holdings = client.get_all_holdings_paginated()

                if not holdings:
                    logger.info("No crypto holdings found")
                    return []

                logger.info(f"Retrieved {len(holdings)} crypto holdings from Robinhood")
                return holdings

        except Exception as e:
            logger.error(f"Error fetching crypto holdings: {e}")
            raise

    def _process_holdings_data(
        self, holdings: List[Dict], db_session
    ) -> List[Dict[str, Any]]:
        """Process holdings data and calculate values"""
        processed_holdings = []

        # Get account currency for symbol formatting
        account_currency = DatabaseOperations.get_account_currency(db_session)

        for holding in holdings:
            try:
                # Extract basic holding data from your Robinhood API response
                asset_code = holding.get("asset_code", "")
                if not asset_code:
                    continue

                # Format symbol as currency pair (e.g., BTC -> BTC-USD)
                symbol = f"{asset_code}-{account_currency}"

                # Get quantities from your API response structure
                total_quantity = float(holding.get("total_quantity", 0))

                # Your API might have different field names, adjust as needed
                available_quantity = float(
                    holding.get("quantity_available_for_trading", 0)
                )
                if available_quantity == 0:
                    # If not available, try other common field names
                    available_quantity = float(
                        holding.get("quantity_available_for_trading", 0)
                    )
                    if available_quantity == 0:
                        available_quantity = (
                            total_quantity  # Default to total if not specified
                        )

                # Skip holdings with zero quantity
                if total_quantity <= 0:
                    continue

                # Try to get price from the holding data first
                price = None

                # Check various possible price fields from your API
                if "price" in holding and holding["price"]:
                    try:
                        price = float(holding["price"])
                    except (ValueError, TypeError):
                        pass

                if price is None and "cost_basis" in holding and holding["cost_basis"]:
                    try:
                        price = float(holding["cost_basis"])
                    except (ValueError, TypeError):
                        pass

                if (
                    price is None
                    and "average_cost" in holding
                    and holding["average_cost"]
                ):
                    try:
                        price = float(holding["average_cost"])
                    except (ValueError, TypeError):
                        pass

                # If no price from holding, get current market price from crypto table
                if price is None:
                    price = DatabaseOperations.get_crypto_price(db_session, symbol)

                # Calculate value
                value = None
                if price is not None and total_quantity > 0:
                    value = total_quantity * price

                holding_data = {
                    "symbol": symbol,
                    "total_quantity": total_quantity,
                    "quantity_available_for_trading": available_quantity,
                    "price": price,
                    "value": value,
                }

                processed_holdings.append(holding_data)
                logger.debug(
                    f"Processed holding for {symbol}: {total_quantity} @ {price}"
                )

            except Exception as e:
                logger.warning(
                    f"Error processing holding {holding.get('asset_code', 'unknown')}: {e}"
                )
                continue

        logger.info(f"Processed {len(processed_holdings)} holdings")
        return processed_holdings

    def collect_and_store(self, db_manager) -> bool:
        """
        Collect holdings data and store in database

        Args:
            db_manager: Database manager instance

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting holdings data collection")

            # Get crypto holdings using your Robinhood API
            holdings = self._get_crypto_holdings()

            # Process holdings data within a database session
            with DatabaseSession(db_manager) as session:
                holdings_data = self._process_holdings_data(holdings, session)

                # Store in database (replace all existing holdings)
                count = DatabaseOperations.replace_holdings_data(session, holdings_data)
                logger.info(f"Successfully stored {count} holdings records")

                return True

        except Exception as e:
            logger.error(f"Failed to collect and store holdings data: {e}")
            return False
