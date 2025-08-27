# data/repositories/crypto_repository.py
"""
Cryptocurrency data repository
Specialized operations for crypto market data
"""
# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation

# Standard Imports
from typing import List, Optional, Dict
from datetime import datetime

# Third Party Imports

# First Party Imports
from database.models import Crypto

# Local Imports
from .base_repository import BaseRepository


class CryptoRepository(BaseRepository[Crypto]):
    """Repository for cryptocurrency market data - Fixed session management"""

    def __init__(self, db_manager):
        super().__init__(db_manager, Crypto)

    def get_by_symbol(self, symbol: str) -> Optional[Crypto]:
        """Get crypto by symbol - returns detached object"""
        with self.get_session() as session:
            crypto = session.query(Crypto).filter(Crypto.symbol == symbol).first() #type:ignore
            if crypto:
                # Detach from session to avoid session binding issues
                session.expunge(crypto) #type:ignore
            return crypto

    def get_monitored_symbols(self) -> List[str]:
        """Get list of monitored crypto symbols"""
        with self.get_session() as session:
            results = (
                session.query(Crypto.symbol).filter(Crypto.monitored).all() #type:ignore
            )
            return [r.symbol for r in results]

    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol - FIXED VERSION"""
        with self.get_session() as session:
            crypto = session.query(Crypto).filter(Crypto.symbol == symbol).first() #type:ignore
            # Return the price value directly, not the object
            return crypto.mid if crypto and crypto.mid else None #type:ignore

    def get_prices_bulk(self, symbols: List[str]) -> Dict[str, float]:
        """Get prices for multiple symbols in one query"""
        prices = {}
        with self.get_session() as session:
            cryptos = session.query(Crypto).filter(Crypto.symbol.in_(symbols)).all() #type:ignore
            for crypto in cryptos:
                if crypto.mid: #type:ignore
                    prices[crypto.symbol] = crypto.mid
        return prices

    def update_prices(self, price_updates: Dict[str, float]) -> int:
        """Batch update prices for multiple symbols"""
        updated_count = 0

        with self.get_session() as session:
            for symbol, price in price_updates.items():
                crypto = session.query(Crypto).filter(Crypto.symbol == symbol).first() #type:ignore

                if crypto:
                    # Update with new mid price
                    crypto.mid = price #type:ignore
                    crypto.updated_at = datetime.utcnow() #type:ignore
                    updated_count += 1

        return updated_count

    def set_monitored_status(self, symbols: List[str], monitored: bool = True) -> int:
        """Set monitored status for multiple symbols"""
        with self.get_session() as session:
            updated = (
                session.query(Crypto) #type:ignore
                .filter(Crypto.symbol.in_(symbols))
                .update(
                    {Crypto.monitored: monitored, Crypto.updated_at: datetime.utcnow()},
                    synchronize_session=False,
                )
            )

            return updated

    def upsert_crypto_data(self, crypto_data: List[Dict]) -> int:
        """Upsert crypto market data"""
        if not crypto_data:
            return 0

        count = 0
        with self.get_session() as session:
            for data in crypto_data:
                symbol = data.get("symbol")
                if not symbol:
                    continue

                existing = session.query(Crypto).filter_by(symbol=symbol).first() #type:ignore

                if existing:
                    # Update existing record
                    for key, value in data.items():
                        if key != "symbol" and hasattr(existing, key):
                            if key != "monitored":
                                setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow() #type:ignore
                else:
                    # Create new record
                    crypto = Crypto(**data)
                    session.add(crypto)  #type:ignore

                count += 1

        return count
