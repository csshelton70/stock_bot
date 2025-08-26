"""
Robinhood Crypto API Configuration Module
========================================

This module provides configuration management for the Robinhood Crypto API client.
It supports loading configuration from JSON files or direct instantiation.

Classes:
    RobinhoodConfig: Configuration dataclass for API settings

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class RobinhoodConfig:
    """
    Configuration class for Robinhood API settings.

    This class holds all configuration parameters needed to interact with the
    Robinhood Crypto API, including authentication and request settings.

    Attributes:
        api_key (str): The API key for authentication
        private_key_base64 (str): Base64 encoded private key for signing requests
        base_url (str): Base URL for the Robinhood API
        request_timeout (int): Request timeout in seconds
        max_retries (int): Maximum number of retry attempts
        backoff_factor (float): Exponential backoff factor for retries
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR)
    """

    api_key: str
    private_key_base64: str
    base_url: str = "https://trading.robinhood.com"
    request_timeout: int = 30
    max_retries: int = 3
    backoff_factor: float = 0.3
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        """
        Validate configuration after initialization.

        Raises:
            ValueError: If required configuration values are missing or invalid
        """
        if not self.api_key:
            raise ValueError("API key is required")
        if not self.private_key_base64:
            raise ValueError("Private key is required")
        if self.request_timeout <= 0:
            raise ValueError("Request timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")
        if self.backoff_factor < 0:
            raise ValueError("Backoff factor must be non-negative")

    @classmethod
    def from_json_file(cls, config_path: Optional[str] = None) -> "RobinhoodConfig":
        """
        Load configuration from a JSON file.

        Args:
            config_path: Path to the JSON configuration file. If None, looks for
                        'config.json' in the current directory, then in the user's
                        home directory under '.robinhood/config.json'

        Returns:
            RobinhoodConfig: Configuration instance loaded from JSON file

        Raises:
            FileNotFoundError: If the configuration file is not found
            ValueError: If required configuration values are missing or invalid
            json.JSONDecodeError: If the JSON file is malformed

        Example:
            >>> # Load from default locations
            >>> config = RobinhoodConfig.from_json_file()

            >>> # Load from specific file
            >>> config = RobinhoodConfig.from_json_file("/path/to/my_config.json")
        """
        if config_path is None:
            # Try common configuration locations
            possible_paths = [
                "config.json",
                "robinhood_config.json",
                os.path.expanduser("~/.robinhood/config.json"),
                os.path.expanduser("~/.config/robinhood/config.json"),
            ]

            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break

            if config_path is None:
                raise FileNotFoundError(
                    f"Configuration file not found. Searched in: {possible_paths}\n"
                    "Create a config.json file or specify the path explicitly."
                )

        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in configuration file {config_path}: {e.msg}",
                e.doc,
                e.pos,
            ) from e

        # Validate required fields
        required_fields = ["api_key", "private_key_base64"]
        missing_fields = [
            field for field in required_fields if field not in config_data
        ]
        if missing_fields:
            raise ValueError(
                f"Missing required fields in configuration file: {missing_fields}"
            )

        # Create configuration with defaults for optional fields
        return cls(
            api_key=config_data["api_key"],
            private_key_base64=config_data["private_key_base64"],
            base_url=config_data.get("base_url", "https://trading.robinhood.com"),
            request_timeout=config_data.get("request_timeout", 30),
            max_retries=config_data.get("max_retries", 3),
            backoff_factor=config_data.get("backoff_factor", 0.3),
            log_level=config_data.get("log_level", "INFO"),
        )

    @classmethod
    def from_env(cls) -> "RobinhoodConfig":
        """
        Load configuration from environment variables (legacy support).

        Environment Variables:
            ROBINHOOD_API_KEY: API key for authentication
            ROBINHOOD_PRIVATE_KEY: Base64 encoded private key
            ROBINHOOD_BASE_URL: API base URL (optional)
            ROBINHOOD_REQUEST_TIMEOUT: Request timeout in seconds (optional)
            ROBINHOOD_MAX_RETRIES: Maximum retry attempts (optional)
            ROBINHOOD_BACKOFF_FACTOR: Backoff factor for retries (optional)
            ROBINHOOD_LOG_LEVEL: Logging level (optional)

        Returns:
            RobinhoodConfig: Configuration instance loaded from environment

        Raises:
            ValueError: If required environment variables are missing

        Note:
            This method is deprecated. Use from_json_file() instead.
        """
        api_key = os.getenv("ROBINHOOD_API_KEY", "")
        private_key = os.getenv("ROBINHOOD_PRIVATE_KEY", "")

        if not api_key:
            raise ValueError("ROBINHOOD_API_KEY environment variable is required")
        if not private_key:
            raise ValueError("ROBINHOOD_PRIVATE_KEY environment variable is required")

        return cls(
            api_key=api_key,
            private_key_base64=private_key,
            base_url=os.getenv("ROBINHOOD_BASE_URL", "https://trading.robinhood.com"),
            request_timeout=int(os.getenv("ROBINHOOD_REQUEST_TIMEOUT", "30")),
            max_retries=int(os.getenv("ROBINHOOD_MAX_RETRIES", "3")),
            backoff_factor=float(os.getenv("ROBINHOOD_BACKOFF_FACTOR", "0.3")),
            log_level=os.getenv("ROBINHOOD_LOG_LEVEL", "INFO"),
        )

    def to_json_file(self, config_path: str, create_dirs: bool = True) -> None:
        """
        Save configuration to a JSON file.

        Args:
            config_path: Path where to save the configuration file
            create_dirs: Whether to create parent directories if they don't exist

        Raises:
            OSError: If file cannot be written or directories cannot be created

        Example:
            >>> config = RobinhoodConfig(api_key="key", private_key_base64="pk")
            >>> config.to_json_file("config.json")
        """
        config_file = Path(config_path)

        if create_dirs:
            config_file.parent.mkdir(parents=True, exist_ok=True)

        config_dict = {
            "api_key": self.api_key,
            "private_key_base64": self.private_key_base64,
            "base_url": self.base_url,
            "request_timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "backoff_factor": self.backoff_factor,
            "log_level": self.log_level,
        }

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dict[str, Any]: Configuration as dictionary
        """
        return {
            "api_key": self.api_key,
            "private_key_base64": self.private_key_base64,
            "base_url": self.base_url,
            "request_timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "backoff_factor": self.backoff_factor,
            "log_level": self.log_level,
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "RobinhoodConfig":
        """
        Create configuration from dictionary.

        Args:
            config_dict: Dictionary containing configuration values

        Returns:
            RobinhoodConfig: Configuration instance

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = ["api_key", "private_key_base64"]
        missing_fields = [
            field for field in required_fields if field not in config_dict
        ]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        return cls(
            api_key=config_dict["api_key"],
            private_key_base64=config_dict["private_key_base64"],
            base_url=config_dict.get("base_url", "https://trading.robinhood.com"),
            request_timeout=config_dict.get("request_timeout", 30),
            max_retries=config_dict.get("max_retries", 3),
            backoff_factor=config_dict.get("backoff_factor", 0.3),
            log_level=config_dict.get("log_level", "INFO"),
        )

    def validate(self) -> bool:
        """
        Validate the current configuration.

        Returns:
            bool: True if configuration is valid

        Raises:
            ValueError: If any configuration value is invalid
        """
        try:
            self.__post_init__()
            return True
        except ValueError:  # pylint:disable=try-except-raise
            raise

    @staticmethod
    def create_example_config(output_path: str = "config.example.json") -> None:
        """
        Create an example configuration file with placeholder values.

        Args:
            output_path: Path where to save the example configuration

        Example:
            >>> RobinhoodConfig.create_example_config("my_config.json")
        """
        example_config = {
            "api_key": "your_api_key_here",
            "private_key_base64": "your_base64_private_key_here",
            "base_url": "https://trading.robinhood.com",
            "request_timeout": 30,
            "max_retries": 3,
            "backoff_factor": 0.3,
            "log_level": "INFO",
        }

        config_file = Path(output_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(example_config, f, indent=2, ensure_ascii=False)

        print(f"Example configuration created at: {output_path}")
        print("Please edit this file with your actual API credentials.")

    def mask_sensitive_data(self) -> Dict[str, Any]:
        """
        Get configuration dictionary with sensitive data masked.

        Returns:
            Dict[str, Any]: Configuration with API key and private key masked

        Example:
            >>> config = RobinhoodConfig.from_json_file()
            >>> safe_config = config.mask_sensitive_data()
            >>> print(safe_config)  # Won't show actual credentials
        """
        masked_config = self.to_dict()
        if self.api_key:
            masked_config["api_key"] = (
                self.api_key[:8] + "..." if len(self.api_key) > 8 else "***"
            )
        if self.private_key_base64:
            masked_config["private_key_base64"] = "***masked***"
        return masked_config
