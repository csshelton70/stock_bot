"""
Robinhood Crypto API Helper Functions Module
===========================================

This module provides convenient helper functions and utilities for working
with the Robinhood Crypto API. It includes factory functions, utility methods,
and common operations to simplify API usage.

Functions:
    create_client: Factory function to create API client instances
    generate_keypair: Generate Ed25519 keypair for API authentication
    validate_symbol: Validate trading pair symbol format
    format_timestamp: Format timestamps for API requests

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

# pylint:disable=broad-exception-caught


import os
import base64
import datetime
import re
from typing import Optional, Tuple

# Import the unified client instead of the old implementation
from robinhood import RobinhoodCryptoAPI
from robinhood import RobinhoodConfig
from robinhood import RobinhoodValidationError

try:
    import nacl.signing

    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False

# pylint:disable=raise-missing-from,broad-exception-raised


def create_client(
    config_path: Optional[str] = None,
    api_key: Optional[str] = None,
    private_key_base64: Optional[str] = None,
    use_env: bool = False,
    **config_kwargs,
) -> RobinhoodCryptoAPI:
    """
    Create a Robinhood Crypto API client with flexible configuration.

    This factory function provides a convenient way to create API client instances
    with various configuration options. It can load configuration from JSON files,
    environment variables, or accept explicit parameters.

    Args:
        config_path: Path to JSON configuration file (if not provided, searches default locations)
        api_key: API key for authentication (overrides config file/env)
        private_key_base64: Private key in base64 format (overrides config file/env)
        use_env: Whether to use environment variables (legacy mode)
        **config_kwargs: Additional configuration parameters to override defaults
            - base_url: API base URL
            - request_timeout: Request timeout in seconds
            - max_retries: Maximum retry attempts
            - backoff_factor: Exponential backoff factor
            - log_level: Logging level

    Returns:
        RobinhoodCryptoAPI: Configured API client instance

    Raises:
        ValueError: If required credentials are missing
        RobinhoodAuthError: If credentials are invalid
        FileNotFoundError: If config file is not found

    Example:
        >>> # Create client from JSON config file (recommended)
        >>> client = create_client()  # Uses config.json from default locations
        >>> client = create_client("my_config.json")  # Uses specific config file

        >>> # Create client with explicit credentials
        >>> client = create_client(
        ...     api_key="your_api_key",
        ...     private_key_base64="your_private_key",
        ...     log_level="DEBUG"
        ... )

        >>> # Create client from environment variables (legacy)
        >>> client = create_client(use_env=True)

        >>> # Create client with config file and overrides
        >>> client = create_client(
        ...     config_path="config.json",
        ...     request_timeout=60,
        ...     log_level="DEBUG"
        ... )
    """
    if api_key and private_key_base64:
        # Create config with explicit credentials
        config = RobinhoodConfig(
            api_key=api_key, private_key_base64=private_key_base64, **config_kwargs
        )
    elif use_env:
        # Load from environment variables (legacy mode)
        config = RobinhoodConfig.from_env()
        # Override with any provided kwargs
        for key, value in config_kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
    else:
        # Load from JSON file (default/recommended mode)
        config = RobinhoodConfig.from_json_file(config_path)
        # Override with any provided kwargs
        for key, value in config_kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

    return RobinhoodCryptoAPI(config)


def generate_keypair() -> Tuple[str, str]:
    """
    Generate an Ed25519 keypair for API authentication.

    This function generates a new Ed25519 keypair that can be used for
    Robinhood API authentication. The private key should be kept secure
    and the public key should be registered with Robinhood.

    Returns:
        Tuple[str, str]: Tuple of (private_key_base64, public_key_base64)

    Raises:
        ImportError: If PyNaCl library is not installed
        Exception: If keypair generation fails

    Example:
        >>> private_key, public_key = generate_keypair()
        >>> print(f"Private Key: {private_key}")
        >>> print(f"Public Key: {public_key}")

    Note:
        Requires PyNaCl library to be installed:
        pip install pynacl
    """
    if not NACL_AVAILABLE:
        raise ImportError(
            "PyNaCl library is required for keypair generation. "
            "Install it with: pip install pynacl"
        )

    try:
        # Generate an Ed25519 keypair
        private_key = nacl.signing.SigningKey.generate()
        public_key = private_key.verify_key

        # Convert keys to base64 strings
        private_key_base64 = base64.b64encode(private_key.encode()).decode()
        public_key_base64 = base64.b64encode(public_key.encode()).decode()

        return private_key_base64, public_key_base64

    except Exception as e:
        raise Exception(f"Failed to generate keypair: {e}")


def create_config_file(
    output_path: str = "config.json",
    api_key: Optional[str] = None,
    private_key_base64: Optional[str] = None,
    interactive: bool = True,
) -> None:
    """
    Create a configuration file interactively or with provided values.

    Args:
        output_path: Where to save the configuration file
        api_key: API key (if not provided and interactive=True, will prompt)
        private_key_base64: Private key (if not provided and interactive=True, will prompt)
        interactive: Whether to prompt for missing values

    Example:
        >>> # Create config file interactively
        >>> create_config_file()

        >>> # Create config file with provided values
        >>> create_config_file(
        ...     "my_config.json",
        ...     api_key="your_key",
        ...     private_key_base64="your_private_key"
        ... )
    """
    if interactive and (not api_key or not private_key_base64):
        print("Creating Robinhood API configuration file...")
        print("You'll need your API key and private key from Robinhood.")

        if not api_key:
            api_key = input("Enter your API key: ").strip()

        if not private_key_base64:
            private_key_base64 = input("Enter your base64 private key: ").strip()

        # Optional settings
        base_url = input(f"Base URL (default: https://trading.robinhood.com): ").strip()
        if not base_url:
            base_url = "https://trading.robinhood.com"

        timeout_str = input("Request timeout in seconds (default: 30): ").strip()
        timeout = int(timeout_str) if timeout_str.isdigit() else 30

        log_level = input("Log level (default: INFO): ").strip().upper()
        if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            log_level = "INFO"
    else:
        base_url = "https://trading.robinhood.com"
        timeout = 30
        log_level = "INFO"

    # Create configuration
    config = RobinhoodConfig(
        api_key=api_key or "",
        private_key_base64=private_key_base64 or "",
        base_url=base_url,
        request_timeout=timeout,
        log_level=log_level,
    )

    # Save to file
    config.to_json_file(output_path)
    print(f"Configuration saved to: {output_path}")


def validate_symbol(symbol: str) -> bool:
    """
    Validate that a trading pair symbol follows the correct format.

    Robinhood trading pair symbols should follow the format: BASE-QUOTE
    where BASE is the base currency and QUOTE is the quote currency.

    Args:
        symbol: Trading pair symbol to validate (e.g., "BTC-USD")

    Returns:
        bool: True if the symbol format is valid

    Raises:
        RobinhoodValidationError: If the symbol format is invalid

    Example:
        >>> validate_symbol("BTC-USD")  # Returns True
        >>> validate_symbol("ETH-USDC")  # Returns True
        >>> validate_symbol("BTCUSD")  # Raises RobinhoodValidationError
    """
    if not isinstance(symbol, str):
        raise RobinhoodValidationError("Symbol must be a string")

    # Pattern: 3-5 uppercase letters, hyphen, 3-5 uppercase letters
    pattern = r"^[A-Z]{2,10}-[A-Z]{2,10}$"

    if not re.match(pattern, symbol):
        raise RobinhoodValidationError(
            f"Invalid symbol format: {symbol}. "
            "Expected format: BASE-QUOTE (e.g., BTC-USD)"
        )

    return True


def validate_asset_code(asset_code: str) -> bool:
    """
    Validate that an asset code follows the correct format.

    Args:
        asset_code: Asset code to validate (e.g., "BTC", "ETH")

    Returns:
        bool: True if the asset code format is valid

    Raises:
        RobinhoodValidationError: If the asset code format is invalid

    Example:
        >>> validate_asset_code("BTC")  # Returns True
        >>> validate_asset_code("ETH")  # Returns True
        >>> validate_asset_code("btc")  # Raises RobinhoodValidationError
    """
    if not isinstance(asset_code, str):
        raise RobinhoodValidationError("Asset code must be a string")

    # Pattern: 2-10 uppercase letters
    pattern = r"^[A-Z]{2,10}$"

    if not re.match(pattern, asset_code):
        raise RobinhoodValidationError(
            f"Invalid asset code format: {asset_code}. "
            "Expected format: 2-10 uppercase letters (e.g., BTC, ETH)"
        )

    return True


def format_timestamp(dt: datetime.datetime) -> str:
    """
    Format a datetime object for API requests.

    Args:
        dt: Datetime object to format

    Returns:
        str: ISO 8601 formatted timestamp string

    Example:
        >>> import datetime
        >>> dt = datetime.datetime.now(datetime.timezone.utc)
        >>> format_timestamp(dt)
        '2023-10-31T20:57:50Z'
    """
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_robinhood_timestamp(timestamp_str: str) -> datetime.datetime:
    """
    Parse a timestamp string from Robinhood API responses.

    Args:
        timestamp_str: Timestamp string from API response

    Returns:
        datetime.datetime: Parsed datetime object with UTC timezone

    Raises:
        ValueError: If timestamp format is invalid

    Example:
        >>> parse_robinhood_timestamp("2023-10-31T20:57:50Z")
        datetime.datetime(2023, 10, 31, 20, 57, 50, tzinfo=datetime.timezone.utc)
    """
    try:
        # Handle different possible formats
        if timestamp_str.endswith("Z"):
            dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
            return dt.replace(tzinfo=datetime.timezone.utc)
        elif "+" in timestamp_str or timestamp_str.endswith("00"):
            # Handle timezone offset formats
            return datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            return datetime.datetime.fromisoformat(timestamp_str)
    except ValueError as e:
        raise ValueError(f"Invalid timestamp format: {timestamp_str}") from e


def calculate_order_value(quantity: float, price: float) -> float:
    """
    Calculate the total value of an order.

    Args:
        quantity: Order quantity
        price: Price per unit

    Returns:
        float: Total order value

    Example:
        >>> calculate_order_value(0.5, 50000.0)  # 0.5 BTC at $50,000
        25000.0
    """
    return quantity * price


def format_currency(amount: float, currency: str = "USD", decimals: int = 2) -> str:
    """
    Format a currency amount for display.

    Args:
        amount: Amount to format
        currency: Currency code (default: "USD")
        decimals: Number of decimal places (default: 2)

    Returns:
        str: Formatted currency string

    Example:
        >>> format_currency(1234.56, "USD")
        '$1,234.56'
        >>> format_currency(0.12345678, "BTC", 8)
        '0.12345678 BTC'
    """
    if currency.upper() == "USD":
        return f"${amount:,.{decimals}f}"
    else:
        return f"{amount:.{decimals}f} {currency.upper()}"


def get_setup_guide() -> str:
    """
    Get a guide for setting up the Robinhood API client.

    Returns:
        str: Setup instructions

    Example:
        >>> print(get_setup_guide())
    """
    return """
Robinhood Crypto API Setup Guide
===============================

Method 1: JSON Configuration File (Recommended)
-----------------------------------------------

1. Create a config.json file in your project directory:
   {
     "api_key": "your_api_key_here",
     "private_key_base64": "your_private_key_here",
     "base_url": "https://trading.robinhood.com",
     "request_timeout": 30,
     "max_retries": 3,
     "backoff_factor": 0.3,
     "log_level": "INFO"
   }

2. Use the client:
   from robinhood_helper import create_client
   client = create_client()  # Automatically finds config.json

Alternative locations for config.json:
  - ./config.json (current directory)
  - ./robinhood_config.json
  - ~/.robinhood/config.json
  - ~/.config/robinhood/config.json

Method 2: Explicit Parameters
----------------------------

from robinhood_helper import create_client
client = create_client(
    api_key="your_api_key",
    private_key_base64="your_private_key"
)

Method 3: Environment Variables (Legacy)
----------------------------------------

Set environment variables:
  export ROBINHOOD_API_KEY="your_api_key_here"
  export ROBINHOOD_PRIVATE_KEY="your_private_key_here"

Then use:
  client = create_client(use_env=True)

Helper Functions
---------------

# Generate new keypair
from robinhood_helper import generate_keypair
private_key, public_key = generate_keypair()

# Create config file interactively
from robinhood_helper import create_config_file
create_config_file()

# Create example config file
from robinhood_config import RobinhoodConfig
RobinhoodConfig.create_example_config()

Getting API Credentials
-----------------------

1. Generate keypair: generate_keypair()
2. Visit: https://robinhood.com/crypto/api
3. Create API credentials using your public key
4. Save your API key and private key to config.json
"""


def get_environment_setup_guide() -> str:
    """
    Get the legacy environment variables setup guide.

    Returns:
        str: Environment setup instructions

    Note:
        This function is deprecated. Use get_setup_guide() instead.
    """
    return """
Legacy Environment Variables Setup (Deprecated)
==============================================

Use JSON configuration files instead. See get_setup_guide() for current instructions.

If you must use environment variables:

export ROBINHOOD_API_KEY="your_api_key_here"
export ROBINHOOD_PRIVATE_KEY="your_private_key_here"
export ROBINHOOD_BASE_URL="https://trading.robinhood.com"  # optional
export ROBINHOOD_REQUEST_TIMEOUT="30"  # optional
export ROBINHOOD_MAX_RETRIES="3"  # optional
export ROBINHOOD_BACKOFF_FACTOR="0.3"  # optional
export ROBINHOOD_LOG_LEVEL="INFO"  # optional

Then use: create_client(use_env=True)
"""


def create_test_client(sandbox: bool = True) -> RobinhoodCryptoAPI:
    """
    Create a client configured for testing.

    Args:
        sandbox: Whether to use sandbox environment (if available)

    Returns:
        RobinhoodCryptoAPI: Test-configured client

    Note:
        This function is for testing purposes and may not work with
        actual Robinhood API endpoints.
    """
    # Note: Robinhood may not have a public sandbox environment
    # This is a placeholder for potential testing configurations

    config_overrides = {
        "log_level": "DEBUG",
        "request_timeout": 60,  # Longer timeout for debugging
    }

    if sandbox and "ROBINHOOD_SANDBOX_URL" in os.environ:
        config_overrides["base_url"] = os.environ["ROBINHOOD_SANDBOX_URL"]

    return create_client(**config_overrides)


# Utility functions for common operations
def get_symbol_parts(symbol: str) -> Tuple[str, str]:
    """
    Split a trading pair symbol into base and quote currencies.

    Args:
        symbol: Trading pair symbol (e.g., "BTC-USD")

    Returns:
        Tuple[str, str]: (base_currency, quote_currency)

    Raises:
        RobinhoodValidationError: If symbol format is invalid

    Example:
        >>> get_symbol_parts("BTC-USD")
        ('BTC', 'USD')
    """
    validate_symbol(symbol)
    parts = symbol.split("-")
    return parts[0], parts[1]


def build_symbol(base: str, quote: str) -> str:
    """
    Build a trading pair symbol from base and quote currencies.

    Args:
        base: Base currency code
        quote: Quote currency code

    Returns:
        str: Trading pair symbol

    Example:
        >>> build_symbol("BTC", "USD")
        'BTC-USD'
    """
    validate_asset_code(base)
    validate_asset_code(quote)
    return f"{base.upper()}-{quote.upper()}"


# Constants for common symbols and assets
COMMON_SYMBOLS = {
    "BTC-USD",
    "ETH-USD",
    "ADA-USD",
    "DOGE-USD",
    "LTC-USD",
    "BCH-USD",
    "ETC-USD",
    "XLM-USD",
    "XRP-USD",
    "LINK-USD",
}

COMMON_ASSETS = {"BTC", "ETH", "ADA", "DOGE", "LTC", "BCH", "ETC", "XLM", "XRP", "LINK"}

USD_STABLECOINS = {"USD", "USDC", "USDT", "BUSD", "DAI"}
