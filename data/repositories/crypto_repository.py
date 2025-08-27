# data/repositories/crypto_repository.py
"""
Cryptocurrency data repository
Specialized operations for crypto market data
"""

from typing import List, Optional, Dict
from sqlalchemy import desc, and_
from datetime import datetime, timedelta

from .base_repository import BaseRepository
from database.models import Crypto


class CryptoRepository(BaseRepository[Crypto]):
    """Repository for cryptocurrency market data - Fixed session management"""

    def __init__(self, db_manager):
        super().__init__(db_manager, Crypto)

    def get_by_symbol(self, symbol: str) -> Optional[Crypto]:
        """Get crypto by symbol - returns detached object"""
        with self.get_session() as session:
            crypto = session.query(Crypto).filter(Crypto.symbol == symbol).first()
            if crypto:
                # Detach from session to avoid session binding issues
                session.expunge(crypto)
            return crypto

    def get_monitored_symbols(self) -> List[str]:
        """Get list of monitored crypto symbols"""
        with self.get_session() as session:
            results = (
                session.query(Crypto.symbol).filter(Crypto.monitored == True).all()
            )
            return [r.symbol for r in results]

    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol - FIXED VERSION"""
        with self.get_session() as session:
            crypto = session.query(Crypto).filter(Crypto.symbol == symbol).first()
            # Return the price value directly, not the object
            return crypto.mid if crypto and crypto.mid else None

    def get_prices_bulk(self, symbols: List[str]) -> Dict[str, float]:
        """Get prices for multiple symbols in one query"""
        prices = {}
        with self.get_session() as session:
            cryptos = session.query(Crypto).filter(Crypto.symbol.in_(symbols)).all()
            for crypto in cryptos:
                if crypto.mid:
                    prices[crypto.symbol] = crypto.mid
        return prices

    def update_prices(self, price_updates: Dict[str, float]) -> int:
        """Batch update prices for multiple symbols"""
        updated_count = 0

        with self.get_session() as session:
            for symbol, price in price_updates.items():
                crypto = session.query(Crypto).filter(Crypto.symbol == symbol).first()

                if crypto:
                    # Update with new mid price
                    crypto.mid = price
                    crypto.updated_at = datetime.utcnow()
                    updated_count += 1

        return updated_count

    def set_monitored_status(self, symbols: List[str], monitored: bool = True) -> int:
        """Set monitored status for multiple symbols"""
        with self.get_session() as session:
            updated = (
                session.query(Crypto)
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

                existing = session.query(Crypto).filter_by(symbol=symbol).first()

                if existing:
                    # Update existing record
                    for key, value in data.items():
                        if key != "symbol" and hasattr(existing, key):
                            if key != "monitored":
                                setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new record
                    crypto = Crypto(**data)
                    session.add(crypto)

                count += 1

        return count
