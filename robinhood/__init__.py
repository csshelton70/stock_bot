"""
Robinhood Crypto API Client Library
===================================

A Python client library for the Robinhood Crypto API providing comprehensive
functionality for cryptocurrency trading, market data, account management,
and portfolio tracking.

Main Classes:
    RobinhoodCryptoAPI: Unified client with all functionality
    RobinhoodConfig: Configuration management

Specialized Clients:
    AccountClient: Account management operations
    MarketDataClient: Market data and trading pairs
    HoldingsClient: Portfolio and holdings management
    OrdersClient: Order placement and management

Enumerations:
    OrderSide: Buy/sell order directions
    OrderType: Market, limit, stop loss, stop limit orders
    OrderState: Order execution states
    TimeInForce: Order validity periods
    EstimatedPriceSide: Price quote sides

Exceptions:
    RobinhoodAPIError: Base API error
    RobinhoodAuthError: Authentication errors
    RobinhoodRateLimitError: Rate limiting errors
    RobinhoodValidationError: Request validation errors
    RobinhoodServerError: Server-side errors

Helper Functions:
    create_client: Factory function for creating API clients
    generate_keypair: Generate Ed25519 keypairs for authentication
    validate_symbol: Validate trading pair symbols
    format_timestamp: Format timestamps for API requests

Usage:
    >>> from robinhood_crypto import RobinhoodCryptoAPI, create_client
    >>>
    >>> # Method 1: Use factory function (recommended)
    >>> with create_client() as client:  # Loads from config.json
    ...     account = client.get_account()
    >>>
    >>> # Method 2: Direct instantiation
    >>> from robinhood_crypto import RobinhoodConfig
    >>> config = RobinhoodConfig.from_json_file("my_config.json")
    >>> with RobinhoodCryptoAPI(config) as client:
    ...     account = client.get_account()
    >>>
    >>> # Method 3: Explicit credentials
    >>> with create_client(
    ...     api_key="your_api_key",
    ...     private_key_base64="your_private_key"
    ... ) as client:
    ...     account = client.get_account()

Version: 1.0.0
Author: Robinhood Crypto API Integration
"""

# Core client classes
from .robinhood_client import RobinhoodCryptoAPI
from .robinhood_config import RobinhoodConfig
from .robinhood_base import RobinhoodBaseClient

# Specialized client classes
from .robinhood_account import AccountClient
from .robinhood_market_data import MarketDataClient
from .robinhood_holdings import HoldingsClient
from .robinhood_orders import OrdersClient

# Enumerations
from .robinhood_enum import (
    OrderSide,
    OrderType,
    OrderState,
    TimeInForce,
    EstimatedPriceSide,
    get_order_side_from_string,
    get_order_type_from_string,
)

# Exception classes
from .robinhood_error import (
    RobinhoodAPIError,
    RobinhoodAuthError,
    RobinhoodRateLimitError,
    RobinhoodValidationError,
    RobinhoodServerError,
    create_error_from_response,
    is_retryable_error,
)

# Helper functions and utilities
from .robinhood_helper import (
    create_client,
    generate_keypair,
    create_config_file,
    validate_symbol,
    validate_asset_code,
    format_timestamp,
    parse_robinhood_timestamp,
    calculate_order_value,
    format_currency,
    get_setup_guide,
    get_environment_setup_guide,
    create_test_client,
    get_symbol_parts,
    build_symbol,
    COMMON_SYMBOLS,
    COMMON_ASSETS,
    USD_STABLECOINS,
)

# Version information
__version__ = "1.0.0"
__author__ = "Robinhood Crypto API Integration"
__license__ = "MIT"

# Define what gets imported with "from robinhood_crypto import *"
__all__ = [
    # Core classes
    "RobinhoodCryptoAPI",
    "RobinhoodConfig",
    "RobinhoodBaseClient",
    # Specialized clients
    "AccountClient",
    "MarketDataClient",
    "HoldingsClient",
    "OrdersClient",
    # Enumerations
    "OrderSide",
    "OrderType",
    "OrderState",
    "TimeInForce",
    "EstimatedPriceSide",
    "get_order_side_from_string",
    "get_order_type_from_string",
    # Exceptions
    "RobinhoodAPIError",
    "RobinhoodAuthError",
    "RobinhoodRateLimitError",
    "RobinhoodValidationError",
    "RobinhoodServerError",
    "create_error_from_response",
    "is_retryable_error",
    # Helper functions
    "create_client",
    "generate_keypair",
    "create_config_file",
    "validate_symbol",
    "validate_asset_code",
    "format_timestamp",
    "parse_robinhood_timestamp",
    "calculate_order_value",
    "format_currency",
    "get_setup_guide",
    "get_environment_setup_guide",
    "create_test_client",
    "get_symbol_parts",
    "build_symbol",
    # Constants
    "COMMON_SYMBOLS",
    "COMMON_ASSETS",
    "USD_STABLECOINS",
    # Version info
    "__version__",
    "__author__",
    "__license__",
]

# Convenience aliases for common use cases
Client = RobinhoodCryptoAPI  # Shorter alias
Config = RobinhoodConfig  # Shorter alias

# Add convenience aliases to __all__
__all__.extend(["Client", "Config"])


def get_version_info():
    """
    Get detailed version and dependency information.

    Returns:
        dict: Version and dependency information
    """
    import sys

    try:
        import requests

        requests_version = requests.__version__
    except ImportError:
        requests_version = "Not installed"

    try:
        import nacl

        nacl_version = nacl.__version__
    except (ImportError, AttributeError):
        nacl_version = "Not installed"

    return {
        "robinhood_crypto_version": __version__,
        "python_version": sys.version,
        "requests_version": requests_version,
        "pynacl_version": nacl_version,
    }


def quick_setup_guide():
    """
    Print a quick setup guide for new users.
    """
    print(
        """
Robinhood Crypto API Quick Setup
================================

1. Install dependencies:
   pip install requests pynacl

2. Generate keypair:
   from robinhood_crypto import generate_keypair
   private_key, public_key = generate_keypair()

3. Create config file:
   from robinhood_crypto import create_config_file
   create_config_file()  # Interactive setup

4. Get API credentials from Robinhood and update config.json

5. Start trading:
   from robinhood_crypto import create_client
   with create_client() as client:
       account = client.get_account()

For detailed documentation, use: get_setup_guide()
    """
    )


# Optional: Perform basic validation on import
def _validate_dependencies():
    """Validate that required dependencies are available."""
    missing_deps = []

    try:
        import requests
    except ImportError:
        missing_deps.append("requests")

    try:
        import nacl.signing
    except ImportError:
        missing_deps.append("pynacl")

    if missing_deps:
        import warnings

        warnings.warn(
            f"Missing optional dependencies: {', '.join(missing_deps)}. "
            f"Install with: pip install {' '.join(missing_deps)}",
            ImportWarning,
        )


# Run dependency validation on import
_validate_dependencies()


# Cleanup namespace - don't expose internal validation function
del _validate_dependencies
