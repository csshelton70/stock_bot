# Robinhood Crypto API Python Client

A comprehensive, production-ready Python library for interacting with the Robinhood Crypto Trading API. This library provides a robust interface with built-in rate limiting, error handling, retry mechanisms, and comprehensive logging.

## Features

- **Complete API Coverage**: Support for all Robinhood Crypto API endpoints
- **Comprehensive Error Handling**: Structured exceptions with detailed error information
- **Automatic Retries**: Exponential backoff for transient failures
- **Configuration Management**: Environment variables and direct configuration support
- **Type Safety**: Full type hints for better IDE support and code reliability
- **Logging**: Detailed logging for debugging and monitoring
- **Context Manager**: Proper resource management with context manager support
- **Pagination**: Helpers for large datasets and code reliability
- **Logging**: Detailed logging for debugging and monitoring
- **Context Manager**: Proper resource management with context manager support

## Installation

### Prerequisites

```bash
pip install requests pynacl
```

### Install the Library

1. Clone or download the library files:
   - `robinhood_api.py`
   - `robinhood_config.py`
   - `robinhood_enum.py`
   - `robinhood_error.py`
   - `robinhood_rate_limiting.py`
   - `robinhood_helper.py`

2. Place these files in your project directory or Python path.

## Quick Start

### 1. Generate API Keys

First, generate an Ed25519 keypair for API authentication:

```python
from robinhood_helper import generate_keypair

# Generate keypair
private_key, public_key = generate_keypair()
print(f"Private Key: {private_key}")
print(f"Public Key: {public_key}")
```

### 2. Create API Credentials

Visit the [Robinhood API Credentials Portal](https://robinhood.com/crypto/api) to:
1. Create your API credentials using the public key generated above
2. Get your API key

### 3. Set Environment Variables

```bash
# Required
export ROBINHOOD_API_KEY="your_api_key_here"
export ROBINHOOD_PRIVATE_KEY="your_private_key_here"

# Optional (with defaults)
export ROBINHOOD_BASE_URL="https://trading.robinhood.com"
export ROBINHOOD_REQUEST_TIMEOUT="30"
export ROBINHOOD_MAX_RETRIES="3"
export ROBINHOOD_BACKOFF_FACTOR="0.3"
export ROBINHOOD_LOG_LEVEL="INFO"
```

### 4. Basic Usage

```python
from robinhood_helper import create_client
from robinhood_enum import OrderSide, OrderType, TimeInForce

# Create client (loads from environment variables)
client = create_client()

# Or create with explicit credentials
client = create_client(
    api_key="your_api_key",
    private_key_base64="your_private_key",
    log_level="DEBUG"
)

try:
    # Get account information
    account = client.get_account()
    print(f"Account: {account}")

    # Get trading pairs
    trading_pairs = client.get_trading_pairs(["BTC-USD", "ETH-USD"])
    print(f"Trading pairs: {trading_pairs}")

    # Get current prices
    prices = client.get_best_bid_ask(["BTC-USD"])
    print(f"BTC-USD prices: {prices}")

    # Get holdings
    holdings = client.get_holdings()
    print(f"Holdings: {holdings}")

    # Place a market order (example - be careful with real money!)
    # order = client.place_market_order(
    #     symbol="BTC-USD",
    #     side=OrderSide.BUY,
    #     quote_amount=10.0  # $10 worth of BTC
    # )
    # print(f"Order placed: {order}")

finally:
    # Always close the client
    client.close()
```

## Advanced Usage

### Using Context Manager

```python
from robinhood_helper import create_client

# Automatic resource cleanup
with create_client() as client:
    account = client.get_account()
    holdings = client.get_holdings()
    # Client automatically closed when exiting the context
```

### Error Handling

```python
from robinhood_helper import create_client
from robinhood_error import (
    RobinhoodAuthError,
    RobinhoodRateLimitError,
    RobinhoodValidationError,
    RobinhoodServerError,
    RobinhoodAPIError
)

client = create_client()

try:
    order = client.place_market_order(
        symbol="BTC-USD",
        side=OrderSide.BUY,
        quote_amount=10.0
    )
except RobinhoodAuthError as e:
    print(f"Authentication failed: {e}")
except RobinhoodValidationError as e:
    print(f"Validation error: {e}")
    print(f"Field errors: {e.get_field_errors()}")
except RobinhoodRateLimitError as e:
    print(f"Rate limit exceeded: {e}")
    if e.retry_after:
        print(f"Retry after {e.retry_after} seconds")
except RobinhoodServerError as e:
    print(f"Server error: {e}")
    if e.is_retryable:
        print("This error might be retryable")
except RobinhoodAPIError as e:
    print(f"API error: {e}")
    print(f"Status code: {e.status_code}")
    print(f"Response data: {e.response_data}")
```

### Order Management

```python
from robinhood_enum import OrderSide, OrderType, TimeInForce

with create_client() as client:
    # Market order
    market_order = client.place_market_order(
        symbol="BTC-USD",
        side=OrderSide.BUY,
        asset_quantity=0.001  # 0.001 BTC
    )

    # Limit order
    limit_order = client.place_limit_order(
        symbol="ETH-USD",
        side=OrderSide.BUY,
        limit_price=2000.0,
        asset_quantity=0.1,
        time_in_force=TimeInForce.GTC
    )

    # Stop loss order
    stop_order = client.place_stop_loss_order(
        symbol="BTC-USD",
        side=OrderSide.SELL,
        stop_price=45000.0,
        asset_quantity=0.001
    )

    # Get order status
    order_status = client.get_order(market_order['id'])
    print(f"Order status: {order_status['state']}")

    # Cancel order if still open
    if order_status['state'] == 'open':
        cancel_result = client.cancel_order(market_order['id'])
        print(f"Order cancelled: {cancel_result}")
```

### Pagination

```python
with create_client() as client:
    # Get all orders (handles pagination automatically)
    all_orders = client.get_all_orders_paginated()
    print(f"Total orders: {len(all_orders)}")

    # Get all holdings
    all_holdings = client.get_all_holdings_paginated()
    print(f"Total holdings: {len(all_holdings)}")

    # Manual pagination
    cursor = None
    page_count = 0
    while True:
        response = client.get_orders(limit=50, cursor=cursor)
        orders = response['results']
        page_count += 1
        print(f"Page {page_count}: {len(orders)} orders")
        
        if not response.get('next'):
            break
        cursor = response['next'].split('cursor=')[1].split('&')[0]
```

### Market Data

```python
from robinhood_enum import EstimatedPriceSide

with create_client() as client:
    # Get best bid/ask for multiple symbols
    prices = client.get_best_bid_ask(["BTC-USD", "ETH-USD", "ADA-USD"])
    
    # Get estimated prices for different quantities
    estimates = client.get_estimated_price(
        symbol="BTC-USD",
        side=EstimatedPriceSide.ASK,  # For buying
        quantities=[0.001, 0.01, 0.1, 1.0]
    )
    
    for result in estimates['results']:
        quantity = result['quantity']
        price = result['price']
        print(f"Buy {quantity} BTC for ~${price}")
```

### Configuration

```python
from robinhood_config import RobinhoodConfig
from robinhood_api import RobinhoodCryptoAPI

# Custom configuration
config = RobinhoodConfig(
    api_key="your_api_key",
    private_key_base64="your_private_key",
    rate_limit_per_minute=50,  # Lower rate limit
    rate_limit_burst=100,
    request_timeout=60,        # Longer timeout
    log_level="DEBUG"
)

client = RobinhoodCryptoAPI(config)
```

## API Reference

### Core Classes

#### `RobinhoodCryptoAPI`
Main API client class with all trading and market data methods.

**Methods:**
- `get_account()` - Get account information
- `get_trading_pairs(symbols=None)` - Get trading pair information
- `get_best_bid_ask(symbols=None)` - Get current best prices
- `get_estimated_price(symbol, side, quantities)` - Get estimated execution prices
- `get_holdings(asset_codes=None)` - Get crypto holdings
- `get_orders(**filters)` - Get orders with filtering
- `get_order(order_id)` - Get specific order
- `place_market_order(...)` - Place market order
- `place_limit_order(...)` - Place limit order
- `place_stop_loss_order(...)` - Place stop loss order
- `place_stop_limit_order(...)` - Place stop limit order
- `cancel_order(order_id)` - Cancel an order

#### `RobinhoodConfig`
Configuration management for API settings.

#### Exception Classes
- `RobinhoodAPIError` - Base exception
- `RobinhoodAuthError` - Authentication errors
- `RobinhoodRateLimitError` - Rate limiting errors
- `RobinhoodValidationError` - Request validation errors
- `RobinhoodServerError` - Server-side errors

### Enums

#### `OrderSide`
- `BUY` - Buy order
- `SELL` - Sell order

#### `OrderType`
- `MARKET` - Market order
- `LIMIT` - Limit order
- `STOP_LOSS` - Stop loss order
- `STOP_LIMIT` - Stop limit order

#### `OrderState`
- `OPEN` - Order is active
- `CANCELED` - Order cancelled
- `PARTIALLY_FILLED` - Partially executed
- `FILLED` - Fully executed
- `FAILED` - Order failed

#### `TimeInForce`
- `GTC` - Good Till Canceled
- `IOC` - Immediate or Cancel
- `FOK` - Fill or Kill

## Rate Limiting

The Robinhood API has server-side rate limiting:

- **Per-minute limit**: 100 requests per minute per user
- **Burst limit**: 300 requests in bursts per user

The library handles rate limit responses automatically through the retry mechanism. When you receive a 429 response, the library will:

1. Catch the `RobinhoodRateLimitError`
2. Extract retry timing from the response headers
3. Implement exponential backoff for retries

```python
# Rate limiting is handled automatically, but you can also handle it manually
try:
    response = client.get_account()
except RobinhoodRateLimitError as e:
    if e.retry_after:
        print(f"Rate limited. Retry after {e.retry_after} seconds")
        time.sleep(e.retry_after)
        # Retry the request
```
```

## Logging

Configure logging to monitor API usage:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or configure specific logger
logger = logging.getLogger('robinhood_api')
logger.setLevel(logging.INFO)
```

## Best Practices

### Security
1. **Never hardcode credentials** in your source code
2. **Use environment variables** for API keys
3. **Encrypt private keys** when storing them
4. **Rotate keys regularly** for enhanced security

### Error Handling
1. **Always use try-catch blocks** for API calls
2. **Handle specific exception types** appropriately
3. **Implement retry logic** for transient failures
4. **Log errors** for debugging and monitoring

### Resource Management
1. **Use context managers** when possible
2. **Always close clients** when done
3. **Respect server-side rate limits** by handling 429 responses
4. **Implement circuit breakers** for production systems

### Testing
1. **Test with small amounts** first
2. **Use paper trading** when available
3. **Validate all parameters** before placing orders
4. **Monitor order execution** carefully

## Examples

### Simple Trading Bot

```python
import time
from robinhood_helper import create_client
from robinhood_enum import OrderSide

def simple_dca_bot(symbol: str, amount: float, interval_seconds: int):
    """Simple Dollar Cost Averaging bot."""
    with create_client() as client:
        while True:
            try:
                # Place small buy order
                order = client.place_market_order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    quote_amount=amount
                )
                print(f"Placed DCA order: {order['id']}")
                
                # Wait for next interval
                time.sleep(interval_seconds)
                
            except Exception as e:
                print(f"Error in DCA bot: {e}")
                time.sleep(60)  # Wait before retrying

# Run DCA bot (buy $10 of BTC every hour)
# simple_dca_bot("BTC-USD", 10.0, 3600)
```

### Portfolio Monitor

```python
from robinhood_helper import create_client, format_currency

def monitor_portfolio():
    """Monitor cryptocurrency portfolio."""
    with create_client() as client:
        # Get all holdings
        holdings = client.get_all_holdings_paginated()
        
        total_value = 0.0
        print("Portfolio Summary:")
        print("-" * 40)
        
        for holding in holdings:
            asset_code = holding['asset_code']
            quantity = float(holding['quantity'])
            
            if quantity > 0:
                # Get current price
                symbol = f"{asset_code}-USD"
                try:
                    price_data = client.get_best_bid_ask([symbol])
                    if price_data['results']:
                        mid_price = (
                            float(price_data['results'][0]['bid_price']) +
                            float(price_data['results'][0]['ask_price'])
                        ) / 2
                        
                        value = quantity * mid_price
                        total_value += value
                        
                        print(f"{asset_code}: {quantity:.8f} @ {format_currency(mid_price)} = {format_currency(value)}")
                    
                except Exception as e:
                    print(f"Error getting price for {symbol}: {e}")
        
        print("-" * 40)
        print(f"Total Portfolio Value: {format_currency(total_value)}")

# monitor_portfolio()
```

### Order Book Analysis

```python
from robinhood_helper import create_client
from robinhood_enum import EstimatedPriceSide

def analyze_order_book(symbol: str):
    """Analyze order book depth for a symbol."""
    with create_client() as client:
        quantities = [0.001, 0.01, 0.1, 1.0, 10.0]
        
        print(f"Order Book Analysis for {symbol}")
        print("=" * 50)
        
        # Get bid prices (for selling)
        bid_estimates = client.get_estimated_price(
            symbol=symbol,
            side=EstimatedPriceSide.BID,
            quantities=quantities
        )
        
        # Get ask prices (for buying)
        ask_estimates = client.get_estimated_price(
            symbol=symbol,
            side=EstimatedPriceSide.ASK,
            quantities=quantities
        )
        
        print("Quantity    Bid Price    Ask Price    Spread")
        print("-" * 50)
        
        for i, qty in enumerate(quantities):
            bid_price = float(bid_estimates['results'][i]['price'])
            ask_price = float(ask_estimates['results'][i]['price'])
            spread = ask_price - bid_price
            spread_pct = (spread / bid_price) * 100
            
            print(f"{qty:8.3f}    ${bid_price:8.2f}    ${ask_price:8.2f}    ${spread:6.2f} ({spread_pct:.2f}%)")

# analyze_order_book("BTC-USD")
```

## Troubleshooting

### Common Issues

#### Authentication Errors
```python
# Check if your keys are correctly formatted
from robinhood_helper import generate_keypair

# Regenerate if needed
private_key, public_key = generate_keypair()
print(f"Use this public key in Robinhood: {public_key}")
```

#### Rate Limiting
```python
# The API has built-in rate limiting on the server side
# Your application should handle 429 responses appropriately

try:
    order = client.place_market_order(...)
except RobinhoodRateLimitError as e:
    print(f"Rate limit hit: {e}")
    if e.retry_after:
        print(f"Retry after {e.retry_after} seconds")
        time.sleep(e.retry_after)
        # Retry the request
```
```

#### Network Issues
```python
# Increase timeout for slow connections
client = create_client(
    request_timeout=60,
    max_retries=5,
    backoff_factor=1.0
)
```

### Debug Mode

```python
import logging

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

client = create_client(log_level="DEBUG")
```

### Health Check

```python
client = create_client()

# Test API connectivity
if client.health_check():
    print("API connection successful")
else:
    print("API connection failed")
```

## Migration Guide

### From Basic Implementation

If you're migrating from the basic implementation provided in the API documentation:

```python
# OLD: Basic implementation
api_trading_client = CryptoAPITrading()
account = api_trading_client.get_account()

# NEW: Enhanced implementation
with create_client() as client:
    account = client.get_account()
```

### Configuration Changes

```python
# OLD: Hardcoded configuration
API_KEY = "your_api_key"
BASE64_PRIVATE_KEY = "your_private_key"

# NEW: Environment-based configuration
# Set environment variables and use:
client = create_client()

# Or explicit configuration:
client = create_client(
    api_key="your_api_key",
    private_key_base64="your_private_key"
)
```

## Contributing

### Development Setup

1. Clone the repository
2. Install dependencies: `pip install requests pynacl`
3. Set up environment variables
4. Run tests: `python -m pytest` (if tests are available)

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all functions
- Add comprehensive docstrings
- Include error handling

### Testing

```python
# Example test
def test_api_client():
    client = create_client()
    assert client.health_check() == True
    client.close()
```

## License

This library is provided as-is for educational and development purposes. Please ensure you comply with Robinhood's Terms of Service and API usage guidelines.

## Disclaimer

**Important**: This library is for educational purposes and should be thoroughly tested before use with real funds. Cryptocurrency trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this library.

- Always test with small amounts first
- Understand the risks involved in cryptocurrency trading
- Comply with all applicable laws and regulations
- Use proper risk management techniques

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the API documentation at Robinhood
3. Ensure your API credentials are correctly configured
4. Check the rate limiting status if requests are failing

## API Documentation References

- [Robinhood Crypto API Documentation](https://docs.robinhood.com/crypto/)
- [API Credentials Portal](https://robinhood.com/crypto/api)
- [Rate Limiting Guidelines](https://docs.robinhood.com/crypto/rate-limiting/)

## Version History

- **v1.0.0**: Initial release with comprehensive API coverage, rate limiting, and error handling