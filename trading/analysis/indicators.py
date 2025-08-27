# trading/analysis/indicators.py
"""
Technical Analysis Indicators
Provides clean separation of indicator calculations from business logic.
"""

import numpy as np
import talib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class IndicatorResult:
    """Base class for indicator results"""

    timestamp: datetime
    symbol: str


@dataclass
class RSIResult(IndicatorResult):
    """RSI indicator result"""

    value: float
    trend: str  # 'rising', 'falling', 'stable'
    crossover: Optional[str] = None  # 'above_70', 'below_30', etc.

    @property
    def is_overbought(self) -> bool:
        return self.value > 70

    @property
    def is_oversold(self) -> bool:
        return self.value < 30


@dataclass
class MACDResult(IndicatorResult):
    """MACD indicator result"""

    macd: float
    signal: float
    histogram: float
    crossover: Optional[str] = None  # 'bullish', 'bearish'

    @property
    def is_bullish_crossover(self) -> bool:
        return self.crossover == "bullish"

    @property
    def is_bearish_crossover(self) -> bool:
        return self.crossover == "bearish"


class TechnicalIndicators:
    """Technical analysis indicators calculator"""

    def __init__(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
    ):
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

    def calculate_rsi(
        self, prices: List[float], symbol: str, timestamps: List[datetime]
    ) -> List[RSIResult]:
        """Calculate RSI with trend analysis"""
        if len(prices) < self.rsi_period + 1:
            return []

        rsi_values = talib.RSI(np.array(prices), timeperiod=self.rsi_period)
        results = []

        for i, (timestamp, rsi_val) in enumerate(zip(timestamps, rsi_values)):
            if np.isnan(rsi_val):
                continue

            # Determine trend
            trend = "stable"
            crossover = None

            if i > 0 and not np.isnan(rsi_values[i - 1]):
                prev_rsi = rsi_values[i - 1]
                if rsi_val > prev_rsi + 1:
                    trend = "rising"
                elif rsi_val < prev_rsi - 1:
                    trend = "falling"

                # Check for crossovers
                if prev_rsi <= 70 and rsi_val > 70:
                    crossover = "above_70"
                elif prev_rsi >= 30 and rsi_val < 30:
                    crossover = "below_30"
                elif prev_rsi >= 70 and rsi_val < 70:
                    crossover = "below_70"
                elif prev_rsi <= 30 and rsi_val > 30:
                    crossover = "above_30"

            results.append(
                RSIResult(
                    timestamp=timestamp,
                    symbol=symbol,
                    value=float(rsi_val),
                    trend=trend,
                    crossover=crossover,
                )
            )

        return results

    def calculate_macd(
        self, prices: List[float], symbol: str, timestamps: List[datetime]
    ) -> List[MACDResult]:
        """Calculate MACD with crossover detection"""
        if len(prices) < max(self.macd_slow, self.macd_signal) + 1:
            return []

        macd, signal, histogram = talib.MACD(
            np.array(prices),
            fastperiod=self.macd_fast,
            slowperiod=self.macd_slow,
            signalperiod=self.macd_signal,
        )

        results = []

        for i, (timestamp, macd_val, signal_val, hist_val) in enumerate(
            zip(timestamps, macd, signal, histogram)
        ):
            if any(np.isnan(x) for x in [macd_val, signal_val, hist_val]):
                continue

            # Detect crossovers
            crossover = None
            if i > 0 and not any(np.isnan(x) for x in [macd[i - 1], signal[i - 1]]):
                prev_macd = macd[i - 1]
                prev_signal = signal[i - 1]

                # Bullish crossover: MACD crosses above signal
                if prev_macd <= prev_signal and macd_val > signal_val:
                    crossover = "bullish"
                # Bearish crossover: MACD crosses below signal
                elif prev_macd >= prev_signal and macd_val < signal_val:
                    crossover = "bearish"

            results.append(
                MACDResult(
                    timestamp=timestamp,
                    symbol=symbol,
                    macd=float(macd_val),
                    signal=float(signal_val),
                    histogram=float(hist_val),
                    crossover=crossover,
                )
            )

        return results
