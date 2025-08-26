# ./utils/config.py

"""
Configuration management for Robinhood Crypto Trading App
"""


# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring,missing-function-docstring, unspecified-encoding,raise-missing-from

import json
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration manager for the application"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file with environment variable overrides"""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Configuration file '{self.config_path}' not found"
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")

        # Override with environment variables if they exist
        config["robinhood"]["api_key"] = os.getenv(
            "ROBINHOOD_API_KEY", config["robinhood"]["api_key"]
        )
        config["robinhood"]["private_key_base64"] = os.getenv(
            "ROBINHOOD_PRIVATE_KEY", config["robinhood"]["private_key_base64"]
        )

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'robinhood.username')"""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def validate(self) -> None:
        """Validate that required configuration values are present"""
        required_keys = [
            "robinhood.api_key",
            "robinhood.private_key_base64",
            "database.path",
            "historical_data.days_back",
            "historical_data.interval_minutes",
            "logging.level",
            "logging.file_path",
        ]

        missing_keys = []
        for key in required_keys:
            if self.get(key) is None:
                missing_keys.append(key)

        if missing_keys:
            raise ValueError(f"Missing required configuration keys: {missing_keys}")

        # Validate credentials are not default values
        api_key = self.get("robinhood.api_key")
        private_key = self.get("robinhood.private_key_base64")

        if (
            api_key == "your_api_key_here"
            or private_key == "your_private_key_base64_here"
        ):
            raise ValueError(
                "Please update robinhood credentials in config.json or set environment variables"
            )

    @property
    def robinhood_api_key(self) -> str:
        return self.get("robinhood.api_key")

    @property
    def robinhood_private_key_base64(self) -> str:
        return self.get("robinhood.private_key_base64")

    @property
    def database_path(self) -> str:
        return self.get("database.path", "crypto_trading.db")

    @property
    def historical_days_back(self) -> int:
        return self.get("historical_data.days_back", 60)

    @property
    def historical_interval_minutes(self) -> int:
        return self.get("historical_data.interval_minutes", 5)

    @property
    def historical_buffer_days(self) -> int:
        return self.get("historical_data.buffer_days", 1)

    @property
    def log_level(self) -> str:
        return self.get("logging.level", "INFO")

    @property
    def log_file_path(self) -> str:
        return self.get("logging.file_path", "logs/app.log")

    @property
    def max_file_size_mb(self) -> int:
        return self.get("logging.max_file_size_mb", 10)

    @property
    def backup_count(self) -> int:
        return self.get("logging.backup_count", 5)

    @property
    def retry_max_attempts(self) -> int:
        return self.get("retry.max_attempts", 3)

    @property
    def retry_backoff_factor(self) -> float:
        return self.get("retry.backoff_factor", 2.0)

    @property
    def retry_initial_delay(self) -> float:
        return self.get("retry.initial_delay", 1.0)
