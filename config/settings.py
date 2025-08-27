# config/settings.py
"""
Centralized configuration management with validation
Replaces scattered configuration across multiple files
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DatabaseConfig:
    """Database configuration"""

    path: str = "crypto_trading.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


@dataclass
class LoggingConfig:
    """Logging configuration"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/app.log"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5


@dataclass
class RobinhoodConfig:
    """Robinhood API configuration"""

    api_key: str = ""
    private_key_base64: str = ""
    base_url: str = "https://trading.robinhood.com"
    request_timeout: int = 30
    max_retries: int = 3


@dataclass
class RetryConfig:
    """Retry configuration"""

    max_attempts: int = 3
    backoff_factor: float = 2.0
    initial_delay: float = 1.0


@dataclass
class TradingConfig:
    """Trading system configuration"""

    monitored_symbols: List[str] = field(default_factory=lambda: ["BTC-USD", "ETH-USD"])
    alert_timeout_hours: int = 12
    strategy_config: Dict[str, Any] = field(
        default_factory=lambda: {
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
        }
    )


@dataclass
class HistoricalIntervalConfig:
    """Configuration for a single historical data interval"""

    interval_minutes: int
    days_back: int = 60
    buffer_days: int = 1
    cleanup_days: int = 90
    enabled: bool = True


@dataclass
class HistoricalConfig:
    """Enhanced historical data collection configuration supporting multiple intervals"""

    # Default intervals with their specific configurations
    intervals: List[HistoricalIntervalConfig] = field(
        default_factory=lambda: [
            HistoricalIntervalConfig(interval_minutes=15, days_back=60, buffer_days=1),
            HistoricalIntervalConfig(interval_minutes=60, days_back=60, buffer_days=1),
        ]
    )

    # Global settings that apply to all intervals
    coinbase_base_url: str = "https://api.exchange.coinbase.com"
    request_delay: float = 0.5
    max_request_delay: float = 5.0
    max_retries: int = 3

    # Backward compatibility properties
    @property
    def days_back(self) -> int:
        """Return days_back from first interval for backward compatibility"""
        return self.intervals[0].days_back if self.intervals else 60

    @property
    def interval_minutes(self) -> int:
        """Return interval_minutes from first interval for backward compatibility"""
        return self.intervals[0].interval_minutes if self.intervals else 15

    @property
    def buffer_days(self) -> int:
        """Return buffer_days from first interval for backward compatibility"""
        return self.intervals[0].buffer_days if self.intervals else 1

    def get_enabled_intervals(self) -> List[HistoricalIntervalConfig]:
        """Get only enabled intervals"""
        return [interval for interval in self.intervals if interval.enabled]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoricalConfig":
        """Create HistoricalConfig from dictionary with backward compatibility"""

        # Handle legacy single interval configuration
        if "interval_minutes" in data:
            # Convert legacy format to new format
            legacy_interval = HistoricalIntervalConfig(
                interval_minutes=data.get("interval_minutes", 15),
                days_back=data.get("days_back", 60),
                buffer_days=data.get("buffer_days", 1),
                cleanup_days=data.get("cleanup_days", 90),
            )
            return cls(
                intervals=[legacy_interval],
                coinbase_base_url=data.get(
                    "coinbase_base_url", "https://api.exchange.coinbase.com"
                ),
                request_delay=data.get("request_delay", 0.5),
                max_request_delay=data.get("max_request_delay", 5.0),
                max_retries=data.get("max_retries", 3),
            )

        # Handle new multi-interval format
        intervals = []
        if "intervals" in data:
            for interval_data in data["intervals"]:
                intervals.append(HistoricalIntervalConfig(**interval_data))
        else:
            # Default intervals if none specified
            intervals = [
                HistoricalIntervalConfig(
                    interval_minutes=15, days_back=60, buffer_days=1
                ),
                HistoricalIntervalConfig(
                    interval_minutes=60, days_back=60, buffer_days=1
                ),
            ]

        return cls(
            intervals=intervals,
            coinbase_base_url=data.get(
                "coinbase_base_url", "https://api.exchange.coinbase.com"
            ),
            request_delay=data.get("request_delay", 0.5),
            max_request_delay=data.get("max_request_delay", 5.0),
            max_retries=data.get("max_retries", 3),
        )


@dataclass
class AppConfig:
    """Main application configuration"""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    robinhood: RobinhoodConfig = field(default_factory=RobinhoodConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    historical: HistoricalConfig = field(default_factory=HistoricalConfig)

    # Migration from old config structure
    @property
    def database_path(self) -> str:
        return self.database.path

    @property
    def retry_max_attempts(self) -> int:
        return self.retry.max_attempts

    @property
    def retry_backoff_factor(self) -> float:
        return self.retry.backoff_factor

    @property
    def retry_initial_delay(self) -> float:
        return self.retry.initial_delay

    @property
    def historical_days_back(self) -> int:
        return self.historical.days_back

    @property
    def historical_buffer_days(self) -> int:
        return self.historical.buffer_days

    @classmethod
    def load(cls, config_path: str) -> "AppConfig":
        """Load configuration from JSON file with environment variable override"""
        config_data = {}

        # Load from file if exists
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_data = json.load(f)

        # Apply environment variable overrides
        config_data = cls._apply_env_overrides(config_data)

        # Create configuration object
        return cls._from_dict(config_data)

    @classmethod
    def _apply_env_overrides(cls, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides"""
        # Robinhood API credentials
        if "robinhood" not in config_data:
            config_data["robinhood"] = {}

        robinhood = config_data["robinhood"]
        robinhood["api_key"] = os.getenv(
            "ROBINHOOD_API_KEY", robinhood.get("api_key", "")
        )
        robinhood["private_key_base64"] = os.getenv(
            "ROBINHOOD_PRIVATE_KEY", robinhood.get("private_key_base64", "")
        )

        # Database path
        if "database" not in config_data:
            config_data["database"] = {}
        config_data["database"]["path"] = os.getenv(
            "DATABASE_PATH", config_data["database"].get("path", "crypto_trading.db")
        )

        # Log level
        if "logging" not in config_data:
            config_data["logging"] = {}
        config_data["logging"]["level"] = os.getenv(
            "LOG_LEVEL", config_data["logging"].get("level", "INFO")
        )

        return config_data

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create AppConfig from dictionary with enhanced historical config support"""

        # Handle legacy config structure
        legacy_config = {}

        # Map legacy historical_data section
        if "historical_data" in data:
            legacy_config["historical"] = data["historical_data"]

        # Merge with new structure
        merged_data = {**data, **legacy_config}

        # Create historical config with proper handling
        historical_data = merged_data.get("historical", {})
        historical_config = HistoricalConfig.from_dict(historical_data)

        return cls(
            database=DatabaseConfig(**merged_data.get("database", {})),
            logging=LoggingConfig(**merged_data.get("logging", {})),
            robinhood=RobinhoodConfig(**merged_data.get("robinhood", {})),
            retry=RetryConfig(**merged_data.get("retry", {})),
            trading=TradingConfig(**merged_data.get("trading", {})),
            historical=historical_config,
        )

    def validate(self) -> None:
        """Validate configuration with improved error messages"""
        errors = []

        # Validate required Robinhood credentials
        if not self.robinhood.api_key:
            errors.append(
                "Robinhood API key is required. Set ROBINHOOD_API_KEY environment variable or add to config.json"
            )
        if not self.robinhood.private_key_base64:
            errors.append(
                "Robinhood private key is required. Set ROBINHOOD_PRIVATE_KEY environment variable or add to config.json"
            )

        # Validate database path
        db_dir = Path(self.database.path).parent
        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create database directory: {e}")

        # Validate log directory
        log_dir = Path(self.logging.file_path).parent
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create log directory: {e}")

        # Validate trading symbols
        if not self.trading.monitored_symbols:
            errors.append("At least one monitored symbol is required")

        # Validate ranges
        if self.historical.days_back <= 0:
            errors.append("Historical days_back must be positive")
        if self.trading.alert_timeout_hours <= 0:
            errors.append("Alert timeout hours must be positive")

        if errors:
            raise ValueError(
                f"Configuration validation failed:\n"
                + "\n".join(f"  - {error}" for error in errors)
            )
