# Robinhood Crypto Trading App - Collectors Architecture Documentation

## Overview

This document describes the data collection architecture for the Robinhood Crypto Trading App. The system uses a modular collector pattern to gather cryptocurrency market data, account information, portfolio holdings, and historical price data from multiple APIs.

**Architecture Pattern:** Collector Pattern with Retry Logic  
**Primary APIs:** Robinhood Crypto API, Coinbase Exchange API  
**Framework:** Python with SQLAlchemy ORM  
**Version:** 1.0.0  
**Last Updated:** August 2025

---

## Architecture Overview

### Design Principles

1. **Separation of Concerns**: Each collector handles one specific type of data
2. **Fault Tolerance**: Built-in retry logic with exponential backoff
3. **API Rate Limiting**: Respectful API usage with delays and limits
4. **Data Integrity**: Transaction-based database operations
5. **Configurability**: All parameters configurable via JSON configuration
6. **Modularity**: Easy to add, modify, or disable collectors

### Collector Workflow

```
Configuration Loading → Database Setup → API Authentication → Data Collection → Storage → Cleanup
```

### Common Architecture Components

**Base Components:**
- Retry logic with exponential backoff
- Database session management
- Comprehensive error handling and logging
- Configurable parameters

**Dependencies:**
- `utils.config`: Configuration management
- `utils.retry`: Retry logic with backoff
- `database.connection`: Database session handling
- `database.operations`: CRUD operations

---

## Collector Implementations

### 1. CryptoCollector - Market Data Collection

**Location:** `collectors/crypto_collector.py`  
**Purpose:** Collect cryptocurrency trading pairs and real-time market prices  
**API Source:** Robinhood Crypto API  
**Target Table:** `crypto`  
**Update Strategy:** Upsert (update existing, insert new)

#### Class Definition
```python
class CryptoCollector:
    def __init__(self, retry_config, api_key: str, private_key_base64: str)
```

#### Key Methods

**`_get_crypto_pairs_and_prices()`**
- Fetches all available trading pairs from Robinhood
- Gets current bid/ask prices for all symbols
- Combines pair metadata with live pricing data
- **Retry Logic:** 3 attempts with exponential backoff
- **API Calls:** 
  - `client.get_all_trading_pairs()`
  - `client.get_best_bid_ask(symbols)`

**`_process_crypto_data(pairs, prices_response)`**
- Merges trading pair metadata with price data
- Calculates mid prices: `(bid + ask) / 2`
- Extracts order size limits (minimum/maximum)
- Handles missing or invalid price data gracefully

**`collect_and_store(db_manager)`**
- Main entry point for crypto data collection
- Coordinates API calls and data processing
- Stores processed data using `DatabaseOperations.upsert_crypto_data()`
- **Transaction Management:** Single transaction for all crypto updates

#### Data Flow
```
Robinhood API → Trading Pairs + Prices → Data Processing → Database Upsert
```

#### Sample Output Processing
```python
# Input: Raw API responses
trading_pairs = [{'symbol': 'BTC-USD', 'min_order_size': '0.000001', ...}, ...]
prices = {'results': [{'symbol': 'BTC-USD', 'bid_price': '45100.00', ...}, ...]}

# Output: Processed records
processed_data = [{
    'symbol': 'BTC-USD',
    'minimum_order': 0.000001,
    'maximum_order': 1000.0,
    'bid': 45100.00,
    'mid': 45125.50,
    'ask': 45151.00
}, ...]
```

#### Error Handling
- API authentication failures
- Network connectivity issues
- Invalid or missing price data
- Database constraint violations

---

### 2. AccountCollector - Account Information

**Location:** `collectors/account_collector.py`  
**Purpose:** Collect Robinhood account details and buying power  
**API Source:** Robinhood Crypto API  
**Target Table:** `account`  
**Update Strategy:** Upsert (should only be one account)

#### Class Definition
```python
class AccountCollector:
    def __init__(self, retry_config, api_key: str, private_key_base64: str)
```

#### Key Methods

**`_get_account_info()`**
- Retrieves account details from Robinhood API
- Extracts account number, status, and buying power
- Enforces USD currency requirement
- **Retry Logic:** 3 attempts with exponential backoff
- **API Calls:** `client.get_account()`

**`collect_and_store(db_manager)`**
- Validates account data completeness
- Ensures account number is present
- Uses `DatabaseOperations.upsert_account_data()` for storage

#### Data Flow
```
Robinhood API → Account Details → Validation → Database Upsert
```

#### Sample Data Processing
```python
# Input: Robinhood account response
account = {
    'account_number': 'RH12345678',
    'status': 'active',
    'buying_power': '5000.50',
    'buying_power_currency': 'USD'
}

# Output: Processed record
account_data = {
    'account_number': 'RH12345678',
    'status': 'active',
    'buying_power': 5000.50,
    'currency': 'USD'
}
```

#### Business Rules
- Only one account per database
- Currency must always be USD
- Account number is required field
- Buying power defaults to 0.0 if not provided

---

### 3. HoldingsCollector - Portfolio Holdings

**Location:** `collectors/holdings_collector.py`  
**Purpose:** Collect current cryptocurrency holdings and calculate values  
**API Source:** Robinhood Crypto API  
**Target Table:** `holdings`  
**Update Strategy:** Complete replacement (delete all, insert fresh)

#### Class Definition
```python
class HoldingsCollector:
    def __init__(self, retry_config, api_key: str, private_key_base64: str)
```

#### Key Methods

**`_get_crypto_holdings()`**
- Fetches all cryptocurrency positions from Robinhood
- Filters out zero-balance positions
- **Retry Logic:** 3 attempts with exponential backoff
- **API Calls:** `client.get_all_holdings_paginated()`

**`_process_holdings_data(holdings, db_session)`**
- Converts asset codes to trading pair symbols (BTC → BTC-USD)
- Calculates position values using current or stored prices
- Handles multiple price sources with fallback logic
- **Price Sources (in priority order):**
  1. API-provided price
  2. Cost basis from holdings
  3. Average cost from holdings
  4. Current market price from crypto table

**`collect_and_store(db_manager)`**
- Uses complete replacement strategy
- Deletes all existing holdings before inserting new data
- **Rationale:** Portfolio positions can change dramatically between updates

#### Data Flow
```
Robinhood API → Holdings → Symbol Formatting → Price Lookup → Value Calculation → Database Replace
```

#### Symbol Processing
```python
# Input: Asset code from API
asset_code = 'BTC'
account_currency = 'USD'  # From account table

# Output: Trading pair symbol
symbol = f"{asset_code}-{account_currency}"  # "BTC-USD"
```

#### Price Resolution Logic
```python
# Priority order for price determination:
1. holding['price']           # Direct API price
2. holding['cost_basis']      # Cost basis as fallback
3. holding['average_cost']    # Average cost as fallback
4. DatabaseOperations.get_crypto_price(symbol)  # Current market price
```

#### Business Rules
- Only holdings with quantity > 0 are stored
- Symbol format: ASSET-USD (always USD quote currency)
- Value = total_quantity × price
- Available quantity defaults to total quantity if not specified

---

### 4. HistoricalCollector - Historical Price Data

**Location:** `collectors/historical_collector.py`  
**Purpose:** Collect historical OHLCV candlestick data for technical analysis  
**API Source:** Coinbase Exchange API  
**Target Table:** `historical`  
**Update Strategy:** Incremental with gap handling

#### Class Definition
```python
class HistoricalCollector:
    def __init__(self, retry_config, days_back: int = 60, interval_minutes: int = 15, buffer_days: int = 1)
```

#### Configuration Parameters
- `days_back`: Initial historical data period (default: 60 days)
- `interval_minutes`: Candlestick interval (default: 15 minutes)
- `buffer_days`: Overlap buffer for incremental updates (default: 1 day)

#### Key Methods

**`_get_monitored_symbols(db_session)`**
- Queries crypto table for symbols with monitored=TRUE
- Only collects historical data for explicitly monitored symbols
- Provides user control over API usage and storage

**`_fetch_initial_data_day_by_day(symbol, db_session)`**
- Used for symbols with no existing historical data
- Fetches data one day at a time to avoid API rate limits
- Handles Coinbase API limitations on data volume per request
- **Strategy:** Sequential daily requests with delays

**`_fetch_incremental_data_from_latest(symbol, db_session)`**
- Used for symbols with existing historical data
- Automatically detects gaps in data collection
- **Gap Detection Logic:**
  - Small gaps (≤7 days): Single API request
  - Large gaps (>7 days): Day-by-day requests
- **Buffer Strategy:** Starts 24 hours before latest record to ensure no gaps

**`_get_single_day_data_from_coinbase(symbol, start, end)`**
- Core API interface to Coinbase Exchange
- Maps interval minutes to Coinbase granularity (seconds)
- Implements rate limiting with configurable delays
- **Retry Logic:** Handles 429 (rate limit) errors with dynamic backoff

#### Data Processing Pipeline

**Symbol Format Conversion:**
```python
# Robinhood format → Coinbase format
'BTC-USD' → 'BTC-USD'  # Same format, validation only
```

**Granularity Mapping:**
```python
# Minutes → Seconds (Coinbase API requirement)
interval_minutes: 1-5    → granularity: 300   (5 min)
interval_minutes: 5-15   → granularity: 900   (15 min)  
interval_minutes: 15-60  → granularity: 3600  (1 hour)
interval_minutes: >60    → granularity: 86400 (1 day)
```

**Data Processing:**
```python
# Input: Coinbase candlestick format
candle = [timestamp, low, high, open, close, volume]

# Output: Database format
record = {
    'symbol': 'BTC-USD',
    'timestamp': datetime.fromtimestamp(timestamp),
    'open': float(open),
    'high': float(high), 
    'low': float(low),
    'close': float(close),
    'volume': float(volume)
}
```

#### Advanced Features

**Smart Gap Handling:**
```python
# Scenario: App hasn't run for 10 days
latest_record = '2025-08-12 14:30:00'
current_time =  '2025-08-22 14:30:00'
gap_days = 10

# Strategy: Day-by-day collection
for day in range(gap_days + buffer_days):
    fetch_single_day(start_date + timedelta(days=day))
```

**Rate Limiting:**
- Base delay: 0.5 seconds between requests
- Dynamic adjustment: Increases on 429 errors
- Max delay: 5.0 seconds
- Respectful API usage patterns

**Error Recovery:**
- Individual day failures don't stop collection
- Continues with remaining days
- Comprehensive logging of successes/failures
- Graceful handling of missing symbols on Coinbase

#### API Rate Limiting Strategy

**Coinbase API Limits:**
- Public API: Generally permissive
- Best practice: 0.5-1 second delays
- 429 handling: Exponential backoff

**Implementation:**
```python
time.sleep(self.request_delay)  # Default: 0.5s
# On 429 error:
self.request_delay = min(self.request_delay * 2, 5.0)
```

---

## Integration and Orchestration

### Main Collection Script

**Location:** `main.py`  
**Class:** `RobinhoodDataCollector`

#### Execution Sequence
```python
def run_data_collection():
    1. CryptoCollector.collect_and_store()      # Market data first
    2. AccountCollector.collect_and_store()     # Account info
    3. HoldingsCollector.collect_and_store()    # Portfolio positions
    4. HistoricalCollector.collect_and_store()  # Price history (monitored only)
```

#### Error Handling Strategy
- **Individual Failures:** One collector failing doesn't stop others
- **Transaction Isolation:** Each collector uses its own database transaction
- **Logging:** Comprehensive logging of all successes and failures
- **Exit Codes:** 0=success, 1=partial failure, 2=critical error

### Configuration Integration

**File:** `config.json`
```json
{
  "robinhood": {
    "api_key": "your_api_key",
    "private_key_base64": "your_private_key"
  },
  "historical_data": {
    "days_back": 60,
    "interval_minutes": 15,
    "buffer_days": 1
  },
  "retry": {
    "max_attempts": 3,
    "backoff_factor": 2,
    "initial_delay": 1
  }
}
```

---

## Error Handling and Resilience

### Retry Logic Implementation

**Base Class:** `utils.retry.retry_with_backoff`
```python
@retry_with_backoff(max_attempts=3, backoff_factor=2.0, initial_delay=1.0)
def api_method(self):
    # API call implementation
```

#### Retry Parameters
- **max_attempts**: Number of retry attempts (default: 3)
- **backoff_factor**: Multiplier for delay between retries (default: 2.0)
- **initial_delay**: Initial delay in seconds (default: 1.0)

#### Retry Scenarios
- Network connectivity issues
- API server errors (5xx responses)
- Authentication token expiration
- Rate limiting (429 responses)

### Database Transaction Management

**Pattern:** Context Manager with Automatic Rollback
```python
with DatabaseSession(db_manager) as session:
    # All database operations
    # Automatic commit on success
    # Automatic rollback on exception
```

### Logging Strategy

**Levels:**
- **DEBUG:** Detailed operation information
- **INFO:** Normal operation flow
- **WARNING:** Recoverable issues
- **ERROR:** Operation failures

**Destinations:**
- **Console:** INFO and above
- **File:** DEBUG and above (complete log)

---

## Performance Characteristics

### Expected API Usage

**Per Collection Cycle:**

**CryptoCollector:**
- Trading pairs: 1 API call
- Price quotes: 1 API call (batch)
- **Total:** 2 API calls

**AccountCollector:**
- Account info: 1 API call
- **Total:** 1 API call

**HoldingsCollector:**
- Holdings: 1 API call (paginated)
- **Total:** 1-3 API calls (depending on pagination)

**HistoricalCollector:**
- **Initial collection:** ~60 API calls (60 days × 1 call per day)
- **Incremental:** 1-7 API calls (depending on gap size)
- **Rate limited:** 0.5 second delays between calls

### Database Performance

**Expected Transaction Sizes:**
- **Crypto:** 100-500 records (upsert)
- **Account:** 1 record (upsert)
- **Holdings:** 10-50 records (replace)
- **Historical:** 1-2,000 records per symbol (insert)

**Storage Impact:**
- **Crypto/Account/Holdings:** Minimal (~1-10 KB)
- **Historical:** ~1-5 MB per symbol per month

### Memory Usage

**Typical Memory Footprint:**
- Base application: ~20-50 MB
- Historical data processing: +10-20 MB per symbol
- Peak usage: ~100-200 MB for 10 symbols

---

## Deployment and Operations

### Scheduling Recommendations

**Frequency Options:**
- **Hourly:** Good for active trading
- **Daily:** Sufficient for long-term analysis
- **Weekly:** Minimal for basic monitoring

**Cron Example (Daily at 6 AM):**
```bash
0 6 * * * cd /path/to/app && python main.py >> logs/cron.log 2>&1
```

### Monitoring and Alerting

**Key Metrics to Monitor:**
- Collection success/failure rates
- API response times
- Database growth rate
- Error frequency by collector

**Log Monitoring:**
```bash
# Check for errors
grep "ERROR" logs/app.log

# Monitor collection status
grep "collection completed" logs/app.log
```

### Maintenance Tasks

**Regular:**
- Monitor log files for errors
- Check database size growth
- Verify data collection completeness

**Periodic:**
- Update monitored symbols as needed
- Review API rate limiting effectiveness
- Archive old historical data if needed

---

## Extensibility and Customization

### Adding New Collectors

**Template Pattern:**
```python
class NewCollector:
    def __init__(self, retry_config, **kwargs):
        self.retry_config = retry_config
        
    @retry_with_backoff(max_attempts=3)
    def _get_data_from_api(self):
        # API calls here
        pass
        
    def _process_data(self, raw_data):
        # Data processing here
        pass
        
    def collect_and_store(self, db_manager) -> bool:
        # Main entry point
        # Return True for success, False for failure
        pass
```

**Integration Steps:**
1. Create collector class following pattern
2. Add to main.py collection sequence
3. Update configuration if needed
4. Add database operations if new table required

### Configuration Extensions

**Adding New Parameters:**
```json
{
  "new_collector": {
    "parameter1": "value1",
    "parameter2": 123
  }
}
```

**Access in Code:**
```python
config.get('new_collector.parameter1')
```

---

## API Dependencies and Limitations

### Robinhood Crypto API

**Authentication:** API Key + Private Key (Base64)  
**Rate Limits:** Generous for authenticated users  
**Data Coverage:** All Robinhood-supported crypto pairs  
**Reliability:** High for basic data, variable for advanced features

**Known Limitations:**
- Limited historical data availability
- Price precision varies by symbol
- Order book depth not available

### Coinbase Exchange API

**Authentication:** Public API (no auth required)  
**Rate Limits:** Generous for public endpoints  
**Data Coverage:** Major cryptocurrencies  
**Reliability:** High for historical data

**Known Limitations:**
- Some altcoins not available (e.g., may not have PEPE-USD)
- Granularity options limited to specific intervals
- Large historical requests may be rejected

**Fallback Strategy:**
- Symbol validation before collection attempts
- Graceful handling of unavailable symbols
- Detailed logging of missing symbols

---

## Security Considerations

### API Credentials

**Storage:** Configuration file or environment variables  
**Format:** Base64-encoded private keys  
**Access:** Restricted to application runtime only

**Best Practices:**
- Never commit credentials to version control
- Use environment variables in production
- Rotate keys periodically
- Monitor for unauthorized access

### Database Security

**Access Control:** File system permissions on SQLite file  
**Data Sensitivity:** Market data (low sensitivity), Account info (medium sensitivity)  
**Encryption:** Consider encrypting database file for sensitive deployments

### Network Security

**API Communication:** HTTPS only  
**Certificate Validation:** Enforced by requests library  
**Data in Transit:** Encrypted via TLS

---

## Troubleshooting Guide

### Common Issues

**"No monitored symbols found"**
- **Cause:** All crypto.monitored flags set to FALSE
- **Solution:** Use `set_monitored_flag.py` to enable monitoring

**"Rate limited by API"**
- **Cause:** Too many requests to Coinbase
- **Solution:** Increase delays, reduce collection frequency

**"Symbol not found on Coinbase"**
- **Cause:** Symbol not supported by Coinbase
- **Solution:** Review symbol list, consider alternative data sources

**Authentication failures**
- **Cause:** Invalid API credentials
- **Solution:** Verify credentials in configuration

### Debugging Steps

1. **Check Logs:** Review app.log for detailed error information
2. **Test Configuration:** Validate config.json syntax and values
3. **Test Connectivity:** Verify network access to APIs
4. **Check Database:** Ensure database file exists and is writable
5. **Verify Credentials:** Test Robinhood API authentication

### Performance Issues

**Slow Historical Collection:**
- Reduce `days_back` parameter
- Increase `interval_minutes` for less granular data
- Consider collecting fewer symbols

**Database Growth:**
- Monitor historical table size
- Consider data archiving strategies
- Optimize query patterns

---

## Version History and Future Plans

### Current Version (1.0.0)

**Features:**
- Complete crypto market data collection
- Account and holdings tracking
- Historical price data with gap handling
- Comprehensive error handling and retry logic

**APIs Integrated:**
- Robinhood Crypto API (primary trading data)
- Coinbase Exchange API (historical data)

### Planned Enhancements

**Version 1.1.0:**
- RSI, MACD, Bollinger Bands calculation collectors
- Trading signal generation
- Enhanced monitoring and alerting

**Version 1.2.0:**
- Additional API sources (Binance, Kraken)
- Real-time data streaming
- Advanced technical indicators

**Version 2.0.0:**
- Machine learning signal generation
- Portfolio optimization suggestions
- Risk management metrics

---

*This document should be updated whenever collector implementations are modified or new collectors are added to maintain accurate documentation.*