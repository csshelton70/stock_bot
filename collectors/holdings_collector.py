# collectors/holdings_collector.py
"""
Refactored holdings collector using repository pattern
"""
from typing import List, Dict, Any
from datetime import datetime

from .base_collector import BaseCollector
from database.connections import DatabaseManager
from database.models import Holdings, Account
from data.repositories.crypto_repository import CryptoRepository
from utils.retry import RetryConfig
from robinhood import RobinhoodCryptoAPI
from database import DatabaseSession


class HoldingsCollector(BaseCollector):
    """Fixed holdings collector with proper session management"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        retry_config: RetryConfig,
        api_client: RobinhoodCryptoAPI,
        crypto_repo: CryptoRepository,
    ):
        super().__init__(db_manager, retry_config)
        self.api_client = api_client
        self.crypto_repo = crypto_repo

    def get_collector_name(self) -> str:
        return "Portfolio Holdings"

    def collect_and_store(self) -> bool:
        """Collect holdings data with fixed session management"""
        try:
            # Get holdings data
            holdings_data = self.api_client.get_all_holdings_paginated()
            if not self.validate_data(holdings_data):
                self.logger.info("No holdings data found")
                holdings_data = []

            # Get account currency for symbol formatting
            account_currency = self._get_account_currency()

            # Get all symbols that will need price lookups
            symbols_needed = set()
            for holding in holdings_data:
                quantity = float(holding.get("total_quantity", 0))
                if quantity > 0:
                    asset_code = holding.get("asset_code", "")
                    if asset_code:
                        symbol = f"{asset_code}-{account_currency}"
                        symbols_needed.add(symbol)

            # Get all prices in one bulk query to avoid session issues
            price_lookup = self.crypto_repo.get_prices_bulk(list(symbols_needed))

            # Process holdings data
            processed_holdings = []
            for holding in holdings_data:
                quantity = float(holding.get("total_quantity", 0))
                if quantity <= 0:
                    continue  # Skip zero holdings

                asset_code = holding.get("asset_code", "")
                if not asset_code:
                    continue

                # Format symbol
                symbol = f"{asset_code}-{account_currency}"

                # Determine price using fallback logic (FIXED)
                price = self._resolve_price_fixed(holding, symbol, price_lookup)

                holding_record = {
                    "symbol": symbol,
                    "total_quantity": quantity,
                    "quantity_available_for_trading": float(
                        holding.get("quantity_available", quantity)
                    ),
                    "price": price,
                    "value": quantity * price if price else None,
                }

                processed_holdings.append(holding_record)

            # Store using complete replacement strategy
            with DatabaseSession(self.db_manager) as db_session:
                # Delete existing holdings
                deleted_count = db_session.query(Holdings).delete()

                # Insert new holdings
                if processed_holdings:
                    holdings_objects = [Holdings(**data) for data in processed_holdings]
                    db_session.add_all(holdings_objects)

            # Log statistics
            total_value = sum(
                h.get("value", 0) for h in processed_holdings if h.get("value")
            )
            self.log_collection_stats(
                {
                    "Holdings processed": len(processed_holdings),
                    "Holdings stored": len(processed_holdings),
                    "Total portfolio value": (
                        f"${total_value:,.2f}" if total_value else "N/A"
                    ),
                }
            )

            return True

        except Exception as e:
            self.logger.error(f"Error in holdings collection: {e}")
            return False

    def _get_account_currency(self) -> str:
        """Get account currency from database"""
        try:
            with DatabaseSession(self.db_manager) as db_session:
                account = db_session.query(Account).first()
                return account.currency if account else "USD"
        except Exception:
            return "USD"  # Default fallback

    def _resolve_price_fixed(
        self, holding: Dict[str, Any], symbol: str, price_lookup: Dict[str, float]
    ) -> float:
        """Resolve price using fallback logic - FIXED VERSION"""
        # Priority 1: Direct API price
        if "price" in holding:
            try:
                return float(holding["price"])
            except (ValueError, TypeError):
                pass

        # Priority 2: Cost basis
        if "cost_basis" in holding:
            try:
                return float(holding["cost_basis"])
            except (ValueError, TypeError):
                pass

        # Priority 3: Average cost
        if "average_cost" in holding:
            try:
                return float(holding["average_cost"])
            except (ValueError, TypeError):
                pass

        # Priority 4: Current market price from price lookup (FIXED)
        if symbol in price_lookup:
            return price_lookup[symbol]

        # Fallback to 0.0 if no price available
        self.logger.warning(f"No price available for {symbol}, using 0.0")
        return 0.0
