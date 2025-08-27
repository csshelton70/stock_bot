# trading/strategies/rsi_macd_strategy.py
"""
RSI + MACD Multi-Timeframe Strategy
Implements the existing trading logic in a modular, testable way
"""

from typing import List, Optional, Dict, Any
from .base_strategy import BaseStrategy, MarketData, TradingSignal
from ..analysis.indicators import TechnicalIndicators, RSIResult, MACDResult


class RSIMACDStrategy(BaseStrategy):
    """
    Multi-timeframe RSI + MACD strategy

    Signal Generation Rules:
    - BUY: RSI oversold recovery + MACD bullish crossover (both timeframes)
    - SELL: RSI overbought + MACD bearish crossover (both timeframes)
    - Confidence based on alignment between timeframes
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.indicators = TechnicalIndicators(
            rsi_period=config.get("rsi_period", 14),
            macd_fast=config.get("macd_fast", 12),
            macd_slow=config.get("macd_slow", 26),
            macd_signal=config.get("macd_signal", 9),
        )
        self.rsi_overbought = config.get("rsi_overbought", 70)
        self.rsi_oversold = config.get("rsi_oversold", 30)

    def get_strategy_name(self) -> str:
        return "RSI_MACD_MultiTimeframe"

    def analyze(
        self, data_15min: List[MarketData], data_1hour: List[MarketData], symbol: str
    ) -> Optional[TradingSignal]:
        """Analyze market data using RSI + MACD strategy"""

        if not self.validate_data(data_15min, data_1hour):
            return None

        # Calculate indicators for both timeframes
        rsi_15min = self._calculate_latest_rsi(data_15min, symbol)
        rsi_1hour = self._calculate_latest_rsi(data_1hour, symbol)
        macd_15min = self._calculate_latest_macd(data_15min, symbol)
        macd_1hour = self._calculate_latest_macd(data_1hour, symbol)

        if not all([rsi_15min, rsi_1hour, macd_15min, macd_1hour]):
            return None

        # Analyze for BUY signals
        buy_signal = self._analyze_buy_signals(
            rsi_15min, rsi_1hour, macd_15min, macd_1hour
        )
        if buy_signal:
            return buy_signal

        # Analyze for SELL signals
        sell_signal = self._analyze_sell_signals(
            rsi_15min, rsi_1hour, macd_15min, macd_1hour
        )
        if sell_signal:
            return sell_signal

        return None

    def validate_data(
        self, data_15min: List[MarketData], data_1hour: List[MarketData]
    ) -> bool:
        """Validate data sufficiency"""
        min_15min_required = (
            max(self.indicators.macd_slow, self.indicators.rsi_period) + 10
        )
        min_1hour_required = (
            max(self.indicators.macd_slow, self.indicators.rsi_period) + 10
        )

        return (
            len(data_15min) >= min_15min_required
            and len(data_1hour) >= min_1hour_required
        )

    def _calculate_latest_rsi(
        self, data: List[MarketData], symbol: str
    ) -> Optional[RSIResult]:
        """Calculate latest RSI value"""
        prices = [d.close for d in data]
        timestamps = [d.timestamp for d in data]

        rsi_results = self.indicators.calculate_rsi(prices, symbol, timestamps)
        return rsi_results[-1] if rsi_results else None

    def _calculate_latest_macd(
        self, data: List[MarketData], symbol: str
    ) -> Optional[MACDResult]:
        """Calculate latest MACD values"""
        prices = [d.close for d in data]
        timestamps = [d.timestamp for d in data]

        macd_results = self.indicators.calculate_macd(prices, symbol, timestamps)
        return macd_results[-1] if macd_results else None

    def _analyze_buy_signals(
        self,
        rsi_15m: RSIResult,
        rsi_1h: RSIResult,
        macd_15m: MACDResult,
        macd_1h: MACDResult,
    ) -> Optional[TradingSignal]:
        """Analyze for BUY signals across timeframes"""
        reasoning = []
        confidence_factors = 0

        # RSI Analysis - Look for oversold recovery
        rsi_15m_bullish = rsi_15m.value < self.rsi_oversold or (
            rsi_15m.value > self.rsi_oversold and rsi_15m.crossover == "above_30"
        )
        rsi_1h_bullish = rsi_1h.value < self.rsi_oversold or (
            rsi_1h.value > self.rsi_oversold and rsi_1h.crossover == "above_30"
        )

        if rsi_15m_bullish:
            reasoning.append(f"15min RSI bullish signal (value: {rsi_15m.value:.2f})")
            confidence_factors += 1

        if rsi_1h_bullish:
            reasoning.append(f"1hour RSI bullish signal (value: {rsi_1h.value:.2f})")
            confidence_factors += 1

        # MACD Analysis - Look for bullish crossovers or positive momentum
        macd_15m_bullish = macd_15m.is_bullish_crossover or (
            macd_15m.macd > macd_15m.signal and macd_15m.histogram > 0
        )
        macd_1h_bullish = macd_1h.is_bullish_crossover or (
            macd_1h.macd > macd_1h.signal and macd_1h.histogram > 0
        )

        if macd_15m_bullish:
            reasoning.append(
                f"15min MACD bullish signal (MACD: {macd_15m.macd:.6f}, Signal: {macd_15m.signal:.6f})"
            )
            confidence_factors += 1

        if macd_1h_bullish:
            reasoning.append(
                f"1hour MACD bullish signal (MACD: {macd_1h.macd:.6f}, Signal: {macd_1h.signal:.6f})"
            )
            confidence_factors += 1

        # Generate signal based on confluence
        if confidence_factors >= 3:  # At least 3 out of 4 factors
            confidence = "HIGH" if confidence_factors == 4 else "MEDIUM"

            return TradingSignal(
                timestamp=rsi_15m.timestamp,
                symbol=rsi_15m.symbol,
                action="BUY",
                confidence=confidence,
                price=0.0,  # Will be filled by caller
                reasoning=reasoning,
                metadata={
                    "rsi_15m": rsi_15m.value,
                    "rsi_1h": rsi_1h.value,
                    "macd_15m": macd_15m.macd,
                    "macd_1h": macd_1h.macd,
                    "confidence_factors": confidence_factors,
                },
            )

        return None

    def _analyze_sell_signals(
        self,
        rsi_15m: RSIResult,
        rsi_1h: RSIResult,
        macd_15m: MACDResult,
        macd_1h: MACDResult,
    ) -> Optional[TradingSignal]:
        """Analyze for SELL signals across timeframes"""
        reasoning = []
        confidence_factors = 0

        # RSI Analysis - Look for overbought conditions
        rsi_15m_bearish = (
            rsi_15m.value > self.rsi_overbought or rsi_15m.crossover == "below_70"
        )
        rsi_1h_bearish = (
            rsi_1h.value > self.rsi_overbought or rsi_1h.crossover == "below_70"
        )

        if rsi_15m_bearish:
            reasoning.append(f"15min RSI bearish signal (value: {rsi_15m.value:.2f})")
            confidence_factors += 1

        if rsi_1h_bearish:
            reasoning.append(f"1hour RSI bearish signal (value: {rsi_1h.value:.2f})")
            confidence_factors += 1

        # MACD Analysis - Look for bearish crossovers or negative momentum
        macd_15m_bearish = macd_15m.is_bearish_crossover or (
            macd_15m.macd < macd_15m.signal and macd_15m.histogram < 0
        )
        macd_1h_bearish = macd_1h.is_bearish_crossover or (
            macd_1h.macd < macd_1h.signal and macd_1h.histogram < 0
        )

        if macd_15m_bearish:
            reasoning.append(
                f"15min MACD bearish signal (MACD: {macd_15m.macd:.6f}, Signal: {macd_15m.signal:.6f})"
            )
            confidence_factors += 1

        if macd_1h_bearish:
            reasoning.append(
                f"1hour MACD bearish signal (MACD: {macd_1h.macd:.6f}, Signal: {macd_1h.signal:.6f})"
            )
            confidence_factors += 1

        # Generate signal based on confluence
        if confidence_factors >= 3:  # At least 3 out of 4 factors
            confidence = "HIGH" if confidence_factors == 4 else "MEDIUM"

            return TradingSignal(
                timestamp=rsi_15m.timestamp,
                symbol=rsi_15m.symbol,
                action="SELL",
                confidence=confidence,
                price=0.0,  # Will be filled by caller
                reasoning=reasoning,
                metadata={
                    "rsi_15m": rsi_15m.value,
                    "rsi_1h": rsi_1h.value,
                    "macd_15m": macd_15m.macd,
                    "macd_1h": macd_1h.macd,
                    "confidence_factors": confidence_factors,
                },
            )

        return None
