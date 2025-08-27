# apps/trading_system_app.py
"""
Refactored Trading System Application
Uses the new modular architecture with dependency injection
"""

from typing import List, Dict, Any, Optional
from core.application import BaseApplication
from trading.strategies.rsi_macd_strategy import RSIMACDStrategy
from trading.alerts.alert_manager import AlertManager
from trading.strategies.base_strategy import TradingSignal, MarketData
from data.repositories.historical_repository import HistoricalRepository
from data.repositories.alert_repository import AlertRepository
from trading.alerts.alert_manager import AlertType


class TradingSystemApp(BaseApplication):
    """Refactored trading system application"""

    def get_app_name(self) -> str:
        return "Robinhood Crypto Trading System"

    def _setup_custom(self) -> None:
        """Setup trading-specific dependencies"""
        # Get shared dependencies
        db_manager = self.context.container.get("db_manager")

        # Register repositories
        self.context.container.register(
            "alert_repo", lambda: AlertRepository(db_manager)
        )
        self.context.container.register(
            "historical_repo", lambda: HistoricalRepository(db_manager)
        )

        # Register strategy
        strategy_config = self.context.config.trading.strategy_config
        self.context.container.register("strategy", RSIMACDStrategy(strategy_config))

        # Register alert manager
        alert_repo = self.context.container.get("alert_repo")
        self.context.container.register(
            "alert_manager", AlertManager(alert_repo, self.context.logger)
        )

    def _run_main(self) -> int:
        """Main trading system logic"""
        try:
            # Get dependencies
            strategy = self.context.container.get("strategy")
            alert_manager = self.context.container.get("alert_manager")
            historical_repo = self.context.container.get("historical_repo")

            # Get monitored symbols
            crypto_repo = self.context.container.get("crypto_repo")
            symbols = crypto_repo.get_monitored_symbols()

            if not symbols:
                symbols = self.context.config.trading.monitored_symbols
                self.context.logger.warning(
                    f"No monitored symbols in database, using config: {symbols}"
                )

            self.context.logger.info(f"Analyzing {len(symbols)} symbols: {symbols}")

            # Expire old alerts
            expired_count = alert_manager.expire_old_alerts(
                self.context.config.trading.alert_timeout_hours
            )

            # Get active alerts
            active_alerts = alert_manager.get_active_alerts()
            self.context.logger.info(f"Found {len(active_alerts)} active alerts")

            # Analyze each symbol
            new_signals = []
            for symbol in symbols:
                try:
                    signal = self._analyze_symbol(
                        symbol, strategy, historical_repo, alert_manager
                    )
                    if signal:
                        new_signals.append(signal)
                except Exception as e:
                    self.context.error_handler.handle_error(
                        e, f"analyzing symbol {symbol}", extra_data={"symbol": symbol}
                    )

            # Output results
            self._output_results(active_alerts, new_signals)

            return 0 if not self.context.error_handler.error_count else 1

        except Exception as e:
            self.context.error_handler.handle_critical_error(e, "main trading logic")
            return 2

    def _analyze_symbol(
        self,
        symbol: str,
        strategy: RSIMACDStrategy,
        historical_repo: HistoricalRepository,
        alert_manager: AlertManager,
    ) -> Optional[TradingSignal]:
        """Analyze a single symbol for trading signals"""

        # Get historical data for both timeframes
        data_15min = self._get_market_data(historical_repo, symbol, "15min", 200)
        data_1hour = self._get_market_data(historical_repo, symbol, "1hour", 200)

        if not data_15min or not data_1hour:
            self.context.logger.warning(f"Insufficient data for {symbol}")
            return None

        # Run strategy analysis
        signal = strategy.analyze(data_15min, data_1hour, symbol)

        if signal:
            # Add current price to signal
            signal.price = data_15min[-1].close

            # Create alert
            alert_type = AlertType.BUY if signal.action == "BUY" else AlertType.SELL
            alert_manager.create_alert(
                symbol=symbol,
                alert_type=alert_type,
                confidence=signal.confidence,
                reasoning=signal.reasoning,
                metadata=signal.metadata,
            )

            self.context.logger.info(
                f"{signal.action} signal for {symbol}: {signal.confidence} confidence at ${signal.price:.2f}"
            )

        return signal

    def _get_market_data(
        self, repo: HistoricalRepository, symbol: str, timeframe: str, limit: int
    ) -> List[MarketData]:
        """Get historical market data converted to MarketData objects"""
        raw_data = repo.get_recent_data(symbol, timeframe, limit)

        # Reverse to get chronological order (oldest first)
        raw_data.reverse()

        return [
            MarketData(
                timestamp=row.timestamp,
                symbol=symbol,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in raw_data
        ]

    def _output_results(
        self, active_alerts: List, new_signals: List[TradingSignal]
    ) -> None:
        """Output analysis results"""
        self.context.logger.info(f"=== Trading Analysis Complete ===")
        self.context.logger.info(f"Active alerts: {len(active_alerts)}")
        self.context.logger.info(f"New signals: {len(new_signals)}")

        for signal in new_signals:
            self.context.logger.info(
                f"NEW {signal.action} SIGNAL: {signal.symbol} at ${signal.price:.2f} "
                f"({signal.confidence} confidence)"
            )
            for reason in signal.reasoning:
                self.context.logger.info(f"  - {reason}")
