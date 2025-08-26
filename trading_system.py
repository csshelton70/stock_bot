#!/usr/bin/env python3
"""
Multi-Timeframe RSI + MACD Trading System - SQLAlchemy ORM Version
Implements 3-stage confirmation trading system for cryptocurrency swing trading
Integrates with existing Robinhood Crypto Trading App architecture using SQLAlchemy ORM
"""

# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring,unused-import

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
#import pandas as pd
import numpy as np
import talib

from database import DatabaseManager, DatabaseOperations
from database import (
    AlertStates,
    SystemLog,
    TradingSignals,
    TechnicalIndicators,
    SignalPerformance,
    Crypto,
)
from database import DatabaseSession,Historical, get_monitored_crypto_symbols
from utils import config
from utils import retry
from robinhood import create_client

from sqlalchemy import desc


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(".\\logs\\trading_system.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


class AlertType(Enum):
    BUY = "buy"
    SELL = "sell"


class AlertStatus(Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"


class ConfidenceLevel(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    REJECT = "REJECT"


@dataclass
class MarketData:
    """Market data for a specific timeframe"""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class RSIAnalysis:
    """RSI analysis results"""

    value: float
    trend: str  # 'rising', 'falling', 'stable'
    crossover: Optional[str] = None  # 'above_70', 'below_30', etc.


@dataclass
class MACDAnalysis:
    """MACD analysis results"""

    macd_line: float
    signal_line: float
    histogram: float
    crossover: str  # 'bullish', 'bearish', 'none'
    histogram_trend: str  # 'rising', 'falling', 'stable'


@dataclass
class TradingSignal:
    """Complete trading signal with analysis"""

    symbol: str
    signal_type: AlertType
    confidence: ConfidenceLevel
    price: float
    timestamp: datetime
    rsi_15min: RSIAnalysis
    rsi_1hour: RSIAnalysis
    macd_15min: MACDAnalysis
    volume_trend: str
    reasoning: List[str]
    alert_id: Optional[int] = None


class DataProvider:
    """Data provider interface for market data using existing architecture"""

    def __init__(self, config: Dict[str, Any], db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.client = None
        try:
            self.client = create_client(api_key = config["robinhood"]["api_key"],private_key_base64 = config["robinhood"]["private_key_base64"])
        except Exception as e:
            logger.warning(f"Could not initialize Robinhood client: {e}")

    def get_historical_data(
        self, symbol: str, timeframe: str, periods: int = 200
    ) -> List[MarketData]:
        """Fetch historical market data using existing database operations"""
        try:
            with self.db_manager.get_session() as session:
                # Try to get data from existing Historical table first
                historical_data = self._fetch_from_database(
                    session, symbol, timeframe, periods
                )

                if (
                    len(historical_data) >= periods // 2
                ):  # At least half the requested data
                    return historical_data
                else:
                    # Fallback to API or mock data
                    logger.info(
                        f"Insufficient database data for {symbol}, using fallback"
                    )
                    return self._generate_mock_data(symbol, periods)

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return self._generate_mock_data(symbol, periods)

    def _fetch_from_database(
        self, session, symbol: str, timeframe: str, periods: int
    ) -> List[MarketData]:
        """Fetch data from existing Historical table"""

        # Map timeframe to interval minutes
        interval_mapping = {"15min": 15, "1hour": 60, "4hour": 240, "1day": 1440}

        interval_minutes = interval_mapping.get(timeframe, 15)

        # Query historical data
        historical_records = (
            session.query(Historical)
            .filter(Historical.symbol == symbol)
            .filter(Historical.interval_minutes == interval_minutes)
            .order_by(desc(Historical.timestamp))
            .limit(periods)
            .all()
        )

        # Convert to MarketData objects
        market_data = []
        for record in reversed(
            historical_records
        ):  # Reverse to get chronological order
            market_data.append(
                MarketData(
                    timestamp=record.timestamp,
                    open=record.open,
                    high=record.high,
                    low=record.low,
                    close=record.close,
                    volume=record.volume or 0.0,
                )
            )

        logger.info(
            f"Retrieved {len(market_data)} historical records for {symbol} ({timeframe})"
        )
        return market_data

    def _generate_mock_data(self, symbol: str, periods: int) -> List[MarketData]:
        """Generate mock market data for testing"""
        logger.info(f"Generating mock data for {symbol} ({periods} periods)")

        data = []
        base_price = (
            50000.0 if "BTC" in symbol else 3000.0 if "ETH" in symbol else 100.0
        )

        for i in range(periods):
            timestamp = datetime.utcnow() - timedelta(minutes=15 * (periods - i))

            # Generate realistic OHLCV data with trends
            volatility = 0.02
            trend_factor = 0.001 * np.sin(i / 20)  # Add some trending
            change = np.random.normal(trend_factor, volatility)

            if i == 0:
                open_price = base_price
            else:
                open_price = data[-1].close

            close_price = open_price * (1 + change)
            high_price = max(open_price, close_price) * (
                1 + abs(np.random.normal(0, 0.01))
            )
            low_price = min(open_price, close_price) * (
                1 - abs(np.random.normal(0, 0.01))
            )
            volume = np.random.uniform(100000, 1000000)

            data.append(
                MarketData(
                    timestamp=timestamp,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                )
            )

        return data


class TechnicalAnalyzer:
    """Technical analysis calculations"""

    @staticmethod
    def calculate_rsi(data: List[MarketData], period: int = 14) -> List[float]:
        """Calculate RSI indicator"""
        closes = np.array([d.close for d in data])
        rsi_values = talib.RSI(closes, timeperiod=period)
        return rsi_values.tolist()

    @staticmethod
    def calculate_macd(
        data: List[MarketData], fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate MACD indicator"""
        closes = np.array([d.close for d in data])
        macd_line, signal_line, histogram = talib.MACD(
            closes, fastperiod=fast, slowperiod=slow, signalperiod=signal
        )
        return macd_line.tolist(), signal_line.tolist(), histogram.tolist()

    @staticmethod
    def analyze_rsi(rsi_values: List[float], lookback: int = 3) -> RSIAnalysis:
        """Analyze RSI for trend and crossovers"""
        if len(rsi_values) < lookback + 1:
            return RSIAnalysis(value=rsi_values[-1], trend="stable")

        current_rsi = rsi_values[-1]
        previous_rsi = rsi_values[-2] if len(rsi_values) >= 2 else current_rsi

        # Determine trend
        recent_values = rsi_values[-lookback:]
        if len(recent_values) >= 2:
            if recent_values[-1] > recent_values[-2] and (
                len(recent_values) < 3 or recent_values[-2] > recent_values[-3]
            ):
                trend = "rising"
            elif recent_values[-1] < recent_values[-2] and (
                len(recent_values) < 3 or recent_values[-2] < recent_values[-3]
            ):
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Check for crossovers
        crossover = None
        if previous_rsi <= 30 < current_rsi:
            crossover = "above_30"
        elif previous_rsi >= 30 > current_rsi:
            crossover = "below_30"
        elif previous_rsi <= 70 < current_rsi:
            crossover = "above_70"
        elif previous_rsi >= 70 > current_rsi:
            crossover = "below_70"

        return RSIAnalysis(value=current_rsi, trend=trend, crossover=crossover)

    @staticmethod
    def analyze_macd(
        macd_line: List[float], signal_line: List[float], histogram: List[float]
    ) -> MACDAnalysis:
        """Analyze MACD for crossovers and trends"""
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        current_hist = histogram[-1]

        previous_macd = macd_line[-2] if len(macd_line) >= 2 else current_macd
        previous_signal = signal_line[-2] if len(signal_line) >= 2 else current_signal

        # Determine crossover
        crossover = "none"
        if previous_macd <= previous_signal and current_macd > current_signal:
            crossover = "bullish"
        elif previous_macd >= previous_signal and current_macd < current_signal:
            crossover = "bearish"

        # Histogram trend
        if len(histogram) >= 3:
            recent_hist = histogram[-3:]
            if all(
                recent_hist[i] < recent_hist[i + 1] for i in range(len(recent_hist) - 1)
            ):
                hist_trend = "rising"
            elif all(
                recent_hist[i] > recent_hist[i + 1] for i in range(len(recent_hist) - 1)
            ):
                hist_trend = "falling"
            else:
                hist_trend = "stable"
        else:
            hist_trend = "stable"

        return MACDAnalysis(
            macd_line=current_macd,
            signal_line=current_signal,
            histogram=current_hist,
            crossover=crossover,
            histogram_trend=hist_trend,
        )


class AlertManager:
    """Manages alert states using SQLAlchemy ORM"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_active_alerts(self) -> List[AlertStates]:
        """Get all active alerts using ORM"""
        with self.db_manager.get_session() as session:
            return (
                session.query(AlertStates)
                .filter(AlertStates.status == AlertStatus.ACTIVE.value)
                .all()
            )

    def create_alert(
        self, symbol: str, alert_type: AlertType, initial_rsi: float
    ) -> int:
        """Create new alert using ORM"""
        with self.db_manager.get_session() as session:
            try:
                # Check if alert already exists for this symbol and type
                existing_alert = (
                    session.query(AlertStates)
                    .filter(AlertStates.symbol == symbol)
                    .filter(AlertStates.alert_type == alert_type.value)
                    .filter(AlertStates.status == AlertStatus.ACTIVE.value)
                    .first()
                )

                if existing_alert:
                    logger.info(f"Alert already exists for {symbol} {alert_type.value}")
                    return existing_alert.id

                # Create new alert
                alert = AlertStates(
                    symbol=symbol,
                    alert_type=alert_type.value,
                    start_time=datetime.utcnow(),
                    rsi_trigger_level=70 if alert_type == AlertType.SELL else 30,
                    initial_rsi=initial_rsi,
                    status=AlertStatus.ACTIVE.value,
                )

                session.add(alert)
                session.flush()  # Get the ID
                alert_id = alert.id
                session.commit()

                self.log_event(
                    symbol,
                    f"ALERT_CREATED_{alert_type.value.upper()}",
                    f"RSI: {initial_rsi:.2f}",
                )

                return alert_id

            except Exception as e:
                session.rollback()
                logger.error(f"Error creating alert: {e}")
                raise

    def update_alert_status(self, alert_id: int, status: AlertStatus):
        """Update alert status using ORM"""
        with self.db_manager.get_session() as session:
            try:
                alert = (
                    session.query(AlertStates)
                    .filter(AlertStates.id == alert_id)
                    .first()
                )
                if alert:
                    alert.status = status.value
                    alert.updated_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Alert {alert_id} status updated to {status.value}")

            except Exception as e:
                session.rollback()
                logger.error(f"Error updating alert status: {e}")
                raise

    def expire_old_alerts(self, timeout_hours: int = 12) -> int:
        """Expire old alerts using ORM helper function"""
        with self.db_manager.get_session() as session:
            try:
                expired_count = cleanup_expired_alerts(session, timeout_hours)
                if expired_count > 0:
                    logger.info(f"Expired {expired_count} old alerts")
                return expired_count

            except Exception as e:
                logger.error(f"Error expiring alerts: {e}")
                return 0

    def log_event(
        self,
        symbol: str,
        event_type: str,
        details: str = None,
        confidence: str = None,
        price: float = None,
    ):
        """Log system event using ORM"""
        with self.db_manager.get_session() as session:
            try:
                log_entry = SystemLog.create_event(
                    symbol=symbol,
                    event_type=event_type,
                    details=details,
                    confidence=confidence,
                    price=price,
                )
                log_entry.timestamp = datetime.utcnow()

                session.add(log_entry)
                session.commit()

            except Exception as e:
                session.rollback()
                logger.error(f"Error logging event: {e}")

    def save_trading_signal(self, signal: TradingSignal):
        """Save trading signal using ORM"""
        with self.db_manager.get_session() as session:
            try:
                signal_record = TradingSignals(
                    symbol=signal.symbol,
                    signal_type=signal.signal_type.value,
                    confidence=signal.confidence.value,
                    price=signal.price,
                    rsi_15min_value=signal.rsi_15min.value,
                    rsi_15min_trend=signal.rsi_15min.trend,
                    rsi_1hour_value=signal.rsi_1hour.value,
                    rsi_1hour_trend=signal.rsi_1hour.trend,
                    macd_line=signal.macd_15min.macd_line,
                    macd_signal_line=signal.macd_15min.signal_line,
                    macd_histogram=signal.macd_15min.histogram,
                    macd_crossover=signal.macd_15min.crossover,
                    volume_trend=signal.volume_trend,
                    reasoning=json.dumps(signal.reasoning),
                    alert_id=signal.alert_id,
                )

                session.add(signal_record)
                session.commit()

                logger.info(
                    f"Saved {signal.confidence.value} {signal.signal_type.value} signal for {signal.symbol}"
                )

            except Exception as e:
                session.rollback()
                logger.error(f"Error saving trading signal: {e}")
                raise


class TradingSystem:
    """Main trading system orchestrator using SQLAlchemy ORM"""

    def __init__(
        self,
        config_path: str = "config.json",
        symbols: List[str] = None,
        db_path: str = "crypto_trading.db",
    ):
        self.config = self._load_config(config_path)
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.create_tables()  # Ensure all tables exist

        # Get monitored symbols from database or use provided list
        if symbols:
            self.symbols = symbols
        else:
            with self.db_manager.get_session() as session:
                monitored_symbols = get_monitored_crypto_symbols(session)
                self.symbols = (
                    monitored_symbols
                    if monitored_symbols
                    else ["BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD"]
                )

        self.data_provider = DataProvider(self.config, self.db_manager)
        self.analyzer = TechnicalAnalyzer()
        self.alert_manager = AlertManager(self.db_manager)

        logger.info(f"Trading system initialized for symbols: {self.symbols}")

    def _load_config(self, config_path: str = "config.json") -> Dict[str, Any]:
        """Load configuration"""
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file {config_path} not found, using defaults")
        except Exception as e:
            logger.error(f"Error loading config: {e}")

        # Default configuration
        return {
            "alert_timeout_hours": 12,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
        }

    def run_analysis(self) -> List[TradingSignal]:
        """Run complete trading analysis"""
        logger.info("Starting trading system analysis...")

        # Expire old alerts first
        self.alert_manager.expire_old_alerts(self.config.get("alert_timeout_hours", 12))

        # Get active alerts
        active_alerts = self.alert_manager.get_active_alerts()
        logger.info(f"Found {len(active_alerts)} active alerts")

        new_signals = []

        for symbol in self.symbols:
            try:
                # Process each symbol for alerts and signals
                new_signal = self._process_symbol(symbol, active_alerts)
                if new_signal:
                    new_signals.append(new_signal)

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                self.alert_manager.log_event(symbol, "ERROR", str(e))

        # Output results
        self._output_results(active_alerts, new_signals)

        logger.info("Trading system analysis completed")
        return new_signals

    def _process_symbol(
        self, symbol: str, active_alerts: List[AlertStates]
    ) -> Optional[TradingSignal]:
        """Process a single symbol for alerts and signals"""
        logger.info(f"Processing {symbol}...")

        # Get market data for both timeframes
        data_15min = self.data_provider.get_historical_data(symbol, "15min", 200)
        data_1hour = self.data_provider.get_historical_data(symbol, "1hour", 200)

        if not data_15min or not data_1hour:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        # Calculate technical indicators
        rsi_15min = self.analyzer.calculate_rsi(data_15min)
        rsi_1hour = self.analyzer.calculate_rsi(data_1hour)
        macd_line, signal_line, histogram = self.analyzer.calculate_macd(data_15min)

        # Analyze indicators
        rsi_15min_analysis = self.analyzer.analyze_rsi(rsi_15min)
        rsi_1hour_analysis = self.analyzer.analyze_rsi(rsi_1hour)
        macd_analysis = self.analyzer.analyze_macd(macd_line, signal_line, histogram)

        current_price = data_15min[-1].close

        # Check for existing alerts for this symbol
        symbol_alerts = [a for a in active_alerts if a.symbol == symbol]

        # Stage 1: Check for new RSI alert triggers
        self._check_new_alert_triggers(symbol, rsi_15min_analysis, current_price)

        # Stage 2 & 3: Process existing alerts
        for alert in symbol_alerts:
            signal = self._evaluate_alert_for_signal(
                alert,
                symbol,
                current_price,
                rsi_15min_analysis,
                rsi_1hour_analysis,
                macd_analysis,
                data_15min,
            )
            if signal:
                return signal

        return None

    def _check_new_alert_triggers(
        self, symbol: str, rsi_15min: RSIAnalysis, price: float
    ):
        """Check for new RSI alert triggers (Stage 1)"""
        # Check for sell alert trigger (RSI crosses above 70)
        if rsi_15min.crossover == "above_70":
            self.alert_manager.create_alert(symbol, AlertType.SELL, rsi_15min.value)
            logger.info(f"Created SELL alert for {symbol} - RSI: {rsi_15min.value:.2f}")

        # Check for buy alert trigger (RSI crosses below 30)
        elif rsi_15min.crossover == "below_30":
            self.alert_manager.create_alert(symbol, AlertType.BUY, rsi_15min.value)
            logger.info(f"Created BUY alert for {symbol} - RSI: {rsi_15min.value:.2f}")

    def _evaluate_alert_for_signal(
        self,
        alert: AlertStates,
        symbol: str,
        price: float,
        rsi_15min: RSIAnalysis,
        rsi_1hour: RSIAnalysis,
        macd_analysis: MACDAnalysis,
        data_15min: List[MarketData],
    ) -> Optional[TradingSignal]:
        """Evaluate if alert should generate trading signal (Stages 2 & 3)"""

        alert_type = AlertType(alert.alert_type)
        hours_active = alert.hours_active

        # Check if alert should trigger
        should_trigger = False

        if alert_type == AlertType.SELL:
            # Sell trigger conditions
            if hours_active <= 2:
                should_trigger = rsi_15min.crossover == "below_70"
            else:
                should_trigger = rsi_15min.value <= 60

        elif alert_type == AlertType.BUY:
            # Buy trigger conditions
            if hours_active <= 2:
                should_trigger = rsi_15min.crossover == "above_30"
            else:
                should_trigger = rsi_15min.value >= 40

        if not should_trigger:
            return None

        # Stage 2: RSI 1-Hour Confirmation
        confidence = self._evaluate_1hour_rsi_confirmation(alert_type, rsi_1hour)

        if confidence == ConfidenceLevel.REJECT:
            self.alert_manager.update_alert_status(alert.id, AlertStatus.EXPIRED)
            self.alert_manager.log_event(
                symbol,
                "SIGNAL_REJECTED",
                f"1-hour RSI confirmation failed: {rsi_1hour.value:.2f}",
            )
            return None

        # Stage 3: MACD Final Confirmation
        confidence, reasoning = self._evaluate_macd_confirmation(
            alert_type, confidence, macd_analysis, data_15min
        )

        # Create trading signal
        signal = TradingSignal(
            symbol=symbol,
            signal_type=alert_type,
            confidence=confidence,
            price=price,
            timestamp=datetime.utcnow(),
            rsi_15min=rsi_15min,
            rsi_1hour=rsi_1hour,
            macd_15min=macd_analysis,
            volume_trend=self._analyze_volume_trend(data_15min),
            reasoning=reasoning,
            alert_id=alert.id,
        )

        # Update alert status and save signal
        self.alert_manager.update_alert_status(alert.id, AlertStatus.TRIGGERED)
        self.alert_manager.save_trading_signal(signal)
        self.alert_manager.log_event(
            symbol,
            f"SIGNAL_GENERATED_{alert_type.value.upper()}",
            f"Confidence: {confidence.value}",
            confidence.value,
            price,
        )

        logger.info(
            f"Generated {confidence.value} confidence {alert_type.value} signal for {symbol}"
        )

        return signal

    def _evaluate_1hour_rsi_confirmation(
        self, alert_type: AlertType, rsi_1hour: RSIAnalysis
    ) -> ConfidenceLevel:
        """Stage 2: Evaluate 1-hour RSI confirmation"""

        if alert_type == AlertType.SELL:
            if rsi_1hour.value > 70:
                return ConfidenceLevel.HIGH
            elif 60 <= rsi_1hour.value <= 70 and rsi_1hour.trend == "falling":
                return ConfidenceLevel.MEDIUM
            elif 50 <= rsi_1hour.value < 60 and rsi_1hour.trend == "falling":
                return ConfidenceLevel.LOW
            else:
                return ConfidenceLevel.REJECT

        elif alert_type == AlertType.BUY:
            if rsi_1hour.value < 30:
                return ConfidenceLevel.HIGH
            elif 30 <= rsi_1hour.value <= 40 and rsi_1hour.trend == "rising":
                return ConfidenceLevel.MEDIUM
            elif 40 < rsi_1hour.value <= 50 and rsi_1hour.trend == "rising":
                return ConfidenceLevel.LOW
            else:
                return ConfidenceLevel.REJECT

        return ConfidenceLevel.REJECT

    def _evaluate_macd_confirmation(
        self,
        alert_type: AlertType,
        current_confidence: ConfidenceLevel,
        macd_analysis: MACDAnalysis,
        data_15min: List[MarketData],
    ) -> Tuple[ConfidenceLevel, List[str]]:
        """Stage 3: MACD final confirmation"""

        reasoning = []
        confidence_adjustments = 0

        if alert_type == AlertType.SELL:
            reasoning.append(
                f"SELL signal - {current_confidence.value} confidence from 1-hour RSI"
            )

            # MACD bearish signals upgrade confidence
            if macd_analysis.crossover == "bearish":
                confidence_adjustments += 1
                reasoning.append("+ MACD bearish crossover detected")

            if macd_analysis.histogram_trend == "falling":
                confidence_adjustments += 1
                reasoning.append("+ MACD histogram declining")

            # MACD bullish signals downgrade confidence
            if (
                macd_analysis.crossover == "bullish"
                or macd_analysis.histogram_trend == "rising"
            ):
                confidence_adjustments -= 1
                reasoning.append("- MACD showing bullish momentum")

        elif alert_type == AlertType.BUY:
            reasoning.append(
                f"BUY signal - {current_confidence.value} confidence from 1-hour RSI"
            )

            # MACD bullish signals upgrade confidence
            if macd_analysis.crossover == "bullish":
                confidence_adjustments += 1
                reasoning.append("+ MACD bullish crossover detected")

            if macd_analysis.histogram_trend == "rising":
                confidence_adjustments += 1
                reasoning.append("+ MACD histogram rising")

            # MACD bearish signals downgrade confidence
            if (
                macd_analysis.crossover == "bearish"
                or macd_analysis.histogram_trend == "falling"
            ):
                confidence_adjustments -= 1
                reasoning.append("- MACD showing bearish momentum")

        # Apply confidence adjustments
        confidence_levels = [
            ConfidenceLevel.LOW,
            ConfidenceLevel.MEDIUM,
            ConfidenceLevel.HIGH,
        ]
        current_index = confidence_levels.index(current_confidence)
        new_index = max(
            0, min(len(confidence_levels) - 1, current_index + confidence_adjustments)
        )
        final_confidence = confidence_levels[new_index]

        if confidence_adjustments > 0:
            reasoning.append(f"Confidence upgraded to {final_confidence.value}")
        elif confidence_adjustments < 0:
            reasoning.append(f"Confidence downgraded to {final_confidence.value}")

        return final_confidence, reasoning

    def _analyze_volume_trend(self, data: List[MarketData], periods: int = 10) -> str:
        """Analyze volume trend"""
        if len(data) < periods:
            return "stable"

        recent_volume = [d.volume for d in data[-periods:]]
        earlier_volume = [d.volume for d in data[-periods * 2 : -periods]]

        if not earlier_volume:
            return "stable"

        recent_avg = sum(recent_volume) / len(recent_volume)
        earlier_avg = sum(earlier_volume) / len(earlier_volume)

        change_ratio = recent_avg / earlier_avg if earlier_avg > 0 else 1.0

        if change_ratio > 1.2:
            return "increasing"
        elif change_ratio < 0.8:
            return "decreasing"
        else:
            return "stable"

    def _output_results(
        self, active_alerts: List[AlertStates], new_signals: List[TradingSignal]
    ):
        """Output analysis results"""
        print("\n" + "=" * 80)
        print("CRYPTO TRADING SYSTEM - ANALYSIS RESULTS")
        print("=" * 80)
        print(f"Analysis Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Monitored Symbols: {', '.join(self.symbols)}")

        # Current Alert Status
        print("\n📊 CURRENT ALERT STATUS:")
        if active_alerts:
            for alert in active_alerts:
                hours_active = alert.hours_active
                print(
                    f"  • {alert.symbol} - {alert.alert_type.upper()} alert "
                    f"({hours_active:.1f}h active, RSI: {alert.initial_rsi:.1f})"
                )
        else:
            print("  No active alerts")

        # New Signals
        print(f"\n🎯 NEW TRADING SIGNALS: {len(new_signals)}")
        if new_signals:
            for signal in new_signals:
                print(
                    f"\n  📈 {signal.symbol} - {signal.signal_type.value.upper()} SIGNAL"
                )
                print(f"     Confidence: {signal.confidence.value}")
                print(f"     Price: ${signal.price:,.2f}")
                print(
                    f"     RSI 15min: {signal.rsi_15min.value:.1f} ({signal.rsi_15min.trend})"
                )
                print(
                    f"     RSI 1hour: {signal.rsi_1hour.value:.1f} ({signal.rsi_1hour.trend})"
                )
                print(
                    f"     MACD: {signal.macd_15min.macd_line:.4f} | Signal: {signal.macd_15min.signal_line:.4f}"
                )
                print(f"     Volume Trend: {signal.volume_trend}")
                print(f"     Reasoning:")
                for reason in signal.reasoning:
                    print(f"       - {reason}")
        else:
            print("  No new signals generated")

        print("\n" + "=" * 80)

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        active_alerts = self.alert_manager.get_active_alerts()

        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "monitored_symbols": self.symbols,
            "active_alerts_count": len(active_alerts),
            "active_alerts": [],
        }

        for alert in active_alerts:
            hours_active = alert.hours_active
            status["active_alerts"].append(
                {
                    "symbol": alert.symbol,
                    "type": alert.alert_type,
                    "hours_active": round(hours_active, 1),
                    "initial_rsi": alert.initial_rsi,
                }
            )

        return status

    def get_performance_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get trading performance summary using ORM"""
        with self.db_manager.get_session() as session:
            from sqlalchemy import func
            from datetime import datetime, timedelta

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Signal counts by confidence
            signal_counts = (
                session.query(
                    TradingSignals.confidence,
                    func.count(TradingSignals.id).label("count"),
                )
                .filter(TradingSignals.created_at >= cutoff_date)
                .group_by(TradingSignals.confidence)
                .all()
            )

            # Most active symbols
            active_symbols = (
                session.query(
                    TradingSignals.symbol,
                    func.count(TradingSignals.id).label("signal_count"),
                )
                .filter(TradingSignals.created_at >= cutoff_date)
                .group_by(TradingSignals.symbol)
                .order_by(func.count(TradingSignals.id).desc())
                .limit(5)
                .all()
            )

            # Alert conversion rate
            total_alerts = (
                session.query(AlertStates)
                .filter(AlertStates.created_at >= cutoff_date)
                .count()
            )

            triggered_alerts = (
                session.query(AlertStates)
                .filter(
                    AlertStates.created_at >= cutoff_date,
                    AlertStates.status == "triggered",
                )
                .count()
            )

            conversion_rate = (
                (triggered_alerts / total_alerts * 100) if total_alerts > 0 else 0
            )

            return {
                "period_days": days,
                "signal_counts": {conf: count for conf, count in signal_counts},
                "most_active_symbols": [
                    {"symbol": sym, "count": count} for sym, count in active_symbols
                ],
                "alert_conversion_rate": round(conversion_rate, 1),
                "total_alerts": total_alerts,
                "triggered_alerts": triggered_alerts,
            }


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Multi-Timeframe RSI + MACD Trading System"
    )
    parser.add_argument(
        "--config", default="config.json", help="Configuration file path"
    )
    parser.add_argument(
        "--db-path", default="crypto_trading.db", help="Database file path"
    )
    parser.add_argument(
        "--symbols", nargs="+", help="Cryptocurrency symbols to monitor"
    )
    parser.add_argument("--status", action="store_true", help="Show system status only")
    parser.add_argument(
        "--performance",
        type=int,
        metavar="DAYS",
        help="Show performance summary for N days",
    )
    parser.add_argument(
        "--test-mode", action="store_true", help="Run with mock data for testing"
    )

    args = parser.parse_args()

    try:
        # Initialize trading system
        trading_system = TradingSystem(
            config_path=args.config, symbols=args.symbols, db_path=args.db_path
        )

        if args.status:
            # Just show status
            status = trading_system.get_system_status()
            print(json.dumps(status, indent=2))
        elif args.performance:
            # Show performance summary
            performance = trading_system.get_performance_summary(args.performance)
            print("\n📊 TRADING PERFORMANCE SUMMARY")
            print(f"Period: Last {performance['period_days']} days")
            print(f"Alert Conversion Rate: {performance['alert_conversion_rate']}%")
            print(
                f"Total Alerts: {performance['total_alerts']} | Triggered: {performance['triggered_alerts']}"
            )

            if performance["signal_counts"]:
                print("\nSignal Confidence Distribution:")
                for conf, count in performance["signal_counts"].items():
                    print(f"  {conf}: {count}")

            if performance["most_active_symbols"]:
                print("\nMost Active Symbols:")
                for symbol_data in performance["most_active_symbols"]:
                    print(f"  {symbol_data['symbol']}: {symbol_data['count']} signals")
        else:
            # Run full analysis
            signals = trading_system.run_analysis()

            # Optional: Return signals for programmatic use
            if signals:
                print(f"\nGenerated {len(signals)} trading signals")

                # Log summary to system log
                high_conf_signals = [
                    s for s in signals if s.confidence == ConfidenceLevel.HIGH
                ]
                if high_conf_signals:
                    for signal in high_conf_signals:
                        trading_system.alert_manager.log_event(
                            signal.symbol,
                            "HIGH_CONFIDENCE_SIGNAL",
                            f"{signal.signal_type.value.upper()} at ${signal.price:,.2f}",
                            "HIGH",
                            signal.price,
                        )

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
    except Exception as e:
        logger.error(f"Trading system error: {e}")
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    # Install required packages if not available
    required_packages = ["pandas", "numpy", "TA-Lib"]
    missing_packages = []

    for package in required_packages:
        try:
            if package == "TA-Lib":
                import talib
            else:
                __import__(package.lower())
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("Missing required packages. Install with:")
        print(f"pip install {' '.join(missing_packages)}")
        print("\nNote: TA-Lib may require additional system dependencies:")
        print("  Ubuntu/Debian: sudo apt-get install libta-lib-dev")
        print("  macOS: brew install ta-lib")
        print(
            "  Windows: Download from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib"
        )
        sys.exit(1)

    sys.exit(main())
