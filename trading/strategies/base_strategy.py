# trading/strategies/base_strategy.py
"""
Base strategy interface for implementing trading strategies
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketData:
    """Market data point"""

    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TradingSignal:
    """Trading signal with confidence and reasoning"""

    timestamp: datetime
    symbol: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'
    price: float
    reasoning: List[str]
    metadata: Dict[str, Any]


class BaseStrategy(ABC):
    """Abstract base class for trading strategies"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.get_strategy_name()

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return strategy name"""
        pass

    @abstractmethod
    def analyze(
        self, data_15min: List[MarketData], data_1hour: List[MarketData], symbol: str
    ) -> Optional[TradingSignal]:
        """
        Analyze market data and generate trading signal

        Args:
            data_15min: 15-minute timeframe data
            data_1hour: 1-hour timeframe data
            symbol: Trading pair symbol

        Returns:
            Trading signal or None if no signal
        """
        pass

    @abstractmethod
    def validate_data(
        self, data_15min: List[MarketData], data_1hour: List[MarketData]
    ) -> bool:
        """Validate that data is sufficient for analysis"""
        pass
