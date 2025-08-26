# Robinhood Crypto Trading App - Database Schema Documentation

## Overview

This document describes the SQLite database schema for the Robinhood Crypto Trading App. The database is designed to store cryptocurrency trading data, account information, portfolio holdings, and historical price data for analysis and trading decision support.

**Database Type:** SQLite  
**File Location:** `crypto_trading.db` (configurable)  
**ORM Framework:** SQLAlchemy 2.0+  
**Version:** 1.0.0  
**Last Updated:** August 2025

---

## Database Architecture

### Base Model Structure

All tables inherit from a common `BaseModel` class that provides standard fields:

```sql
-- Common fields for all tables
id           INTEGER PRIMARY KEY AUTOINCREMENT
created_at   DATETIME NOT NULL DEFAULT (datetime('now'))
updated_at   DATETIME NOT NULL DEFAULT (datetime('now'))
```

**Field Descriptions:**
- `id`: Auto-incrementing primary key for all records
- `created_at`: Timestamp when the record was first created (UTC)
- `updated_at`: Timestamp when the record was last modified (UTC, auto-updated)

---

## Table Schemas

### 1. `crypto` - Cryptocurrency Pairs and Market Data

Stores cryptocurrency trading pairs, current market prices, and monitoring configuration.

```sql
CREATE TABLE crypto (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          VARCHAR(20) UNIQUE NOT NULL,
    minimum_order   FLOAT,
    maximum_order   FLOAT,
    bid             FLOAT,
    mid             FLOAT,
    ask             FLOAT,
    monitored       BOOLEAN NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL
);

-- Indexes
CREATE INDEX ix_crypto_symbol ON crypto (symbol);
```

**Field Descriptions:**
- `symbol`: Trading pair symbol (e.g., "BTC-USD", "ETH-USD")
- `minimum_order`: Minimum order size allowed for this pair
- `maximum_order`: Maximum order size allowed for this pair
- `bid`: Current highest bid price
- `mid`: Mid-market price, calculated as (bid + ask) / 2
- `ask`: Current lowest ask price
- `monitored`: Boolean flag indicating if this pair should be monitored for historical data collection

**Data Sources:** Robinhood API via `CryptoCollector`  
**Update Frequency:** Each time the main data collection script runs  
**Sample Data:**
```
symbol    | min_order | max_order | bid      | mid      | ask      | monitored
BTC-USD   | 0.000001  | 1000.0    | 45123.45 | 45125.50 | 45127.55 | 1
ETH-USD   | 0.00001   | 5000.0    | 2456.78  | 2457.89  | 2459.00  | 1
PEPE-USD  | 1000.0    | 1000000.0 | 0.000012 | 0.000013 | 0.000014 | 0
```

---

### 2. `account` - Account Information

Stores Robinhood account details and buying power information.

```sql
CREATE TABLE account (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number  VARCHAR(50) UNIQUE NOT NULL,
    status          VARCHAR(20),
    buying_power    FLOAT,
    currency        VARCHAR(10) NOT NULL DEFAULT 'USD',
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL
);

-- Indexes
CREATE INDEX ix_account_account_number ON account (account_number);
```

**Field Descriptions:**
- `account_number`: Unique Robinhood account identifier
- `status`: Account status (e.g., "active", "pending", "restricted")
- `buying_power`: Available buying power in account currency
- `currency`: Account currency (always "USD" per requirements)

**Data Sources:** Robinhood API via `AccountCollector`  
**Update Frequency:** Each time the main data collection script runs  
**Cardinality:** One record per account (typically only one record total)  
**Sample Data:**
```
account_number | status | buying_power | currency
RH12345678     | active | 5000.50      | USD
```

---

### 3. `holdings` - Portfolio Holdings

Stores current cryptocurrency holdings and their calculated values.

```sql
CREATE TABLE holdings (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol                          VARCHAR(20) NOT NULL,
    total_quantity                  FLOAT NOT NULL DEFAULT 0.0,
    quantity_available_for_trading  FLOAT NOT NULL DEFAULT 0.0,
    price                           FLOAT,
    value                           FLOAT,
    created_at                      DATETIME NOT NULL,
    updated_at                      DATETIME NOT NULL
);

-- Indexes
CREATE INDEX ix_holdings_symbol ON holdings (symbol);
CREATE INDEX idx_holdings_symbol_updated ON holdings (symbol, updated_at);
```

**Field Descriptions:**
- `symbol`: Cryptocurrency trading pair (e.g., "BTC-USD")
- `total_quantity`: Total quantity of the asset owned
- `quantity_available_for_trading`: Quantity available for trading (excluding pending orders)
- `price`: Current or last known price per unit
- `value`: Total value calculated as total_quantity × price

**Data Sources:** Robinhood API via `HoldingsCollector`  
**Update Frequency:** Each time the main data collection script runs  
**Data Management:** Complete replacement on each update (old records deleted)  
**Sample Data:**
```
symbol  | total_quantity | available_qty | price     | value
BTC-USD | 0.1234567      | 0.1234567     | 45125.50  | 5567.89
ETH-USD | 2.5678901      | 2.0000000     | 2457.89   | 6312.45
```

---

### 4. `historical` - Historical Price Data (OHLCV)

Stores historical candlestick data for technical analysis and charting.

```sql
CREATE TABLE historical (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      VARCHAR(20) NOT NULL,
    timestamp   DATETIME NOT NULL,
    open        FLOAT NOT NULL,
    high        FLOAT NOT NULL,
    low         FLOAT NOT NULL,
    close       FLOAT NOT NULL,
    volume      FLOAT DEFAULT 0.0,
    created_at  DATETIME NOT NULL,
    updated_at  DATETIME NOT NULL,
    
    -- Constraints
    CONSTRAINT uix_symbol_timestamp UNIQUE (symbol, timestamp)
);

-- Indexes
CREATE INDEX ix_historical_symbol ON historical (symbol);
CREATE INDEX ix_historical_timestamp ON historical (timestamp);
CREATE INDEX idx_historical_symbol_timestamp ON historical (symbol, timestamp);
```

**Field Descriptions:**
- `symbol`: Cryptocurrency trading pair (e.g., "BTC-USD")
- `timestamp`: Candlestick timestamp (start of the period)
- `open`: Opening price for the time period
- `high`: Highest price during the time period
- `low`: Lowest price during the time period
- `close`: Closing price for the time period
- `volume`: Trading volume during the time period

**Data Sources:** Coinbase API via `HistoricalCollector`  
**Update Frequency:** Each time the main data collection script runs  
**Data Interval:** Configurable (default: 15 minutes)  
**Duplicate Prevention:** Unique constraint on (symbol, timestamp)  
**Sample Data:**
```
symbol  | timestamp           | open     | high     | low      | close    | volume
BTC-USD | 2025-08-22 14:00:00 | 45100.00 | 45200.00 | 45050.00 | 45150.00 | 1234567
BTC-USD | 2025-08-22 14:15:00 | 45150.00 | 45180.00 | 45120.00 | 45165.00 | 987654
```

---

## Relationships and Data Flow

### Data Collection Flow

```
1. CryptoCollector → crypto table (trading pairs, prices)
2. AccountCollector → account table (account info)
3. HoldingsCollector → holdings table (portfolio positions)
4. HistoricalCollector → historical table (price history for monitored symbols)
```

### Table Relationships

```
crypto.symbol ←→ holdings.symbol (logical relationship)
crypto.monitored = TRUE → historical.symbol (filtered collection)
crypto.mid → holdings.price (price lookup fallback)
account.currency → holdings.symbol formatting (symbol creation)
```

### Data Dependencies

- **Holdings**: Depends on crypto table for price information when not provided by API
- **Historical**: Only collects data for symbols where crypto.monitored = TRUE
- **Symbol Formatting**: Uses account.currency to format asset codes into trading pairs

---

## Indexes and Performance

### Primary Indexes

All tables have automatic primary key indexes on the `id` field.

### Custom Indexes

**crypto table:**
- `ix_crypto_symbol`: Unique index on symbol for fast lookups

**account table:**
- `ix_account_account_number`: Unique index on account_number

**holdings table:**
- `ix_holdings_symbol`: Index on symbol for filtering
- `idx_holdings_symbol_updated`: Composite index on (symbol, updated_at) for efficient queries

**historical table:**
- `ix_historical_symbol`: Index on symbol for filtering by trading pair
- `ix_historical_timestamp`: Index on timestamp for time-based queries
- `idx_historical_symbol_timestamp`: Composite index for optimal range queries
- `uix_symbol_timestamp`: Unique constraint preventing duplicate records

### Query Optimization

Common query patterns are optimized through strategic indexing:

```sql
-- Fast symbol lookup (uses ix_crypto_symbol)
SELECT * FROM crypto WHERE symbol = 'BTC-USD';

-- Efficient holdings retrieval (uses ix_holdings_symbol)
SELECT * FROM holdings WHERE total_quantity > 0;

-- Optimized historical data queries (uses idx_historical_symbol_timestamp)
SELECT * FROM historical 
WHERE symbol = 'BTC-USD' 
  AND timestamp >= '2025-08-01' 
ORDER BY timestamp;

-- Monitored symbols query (uses ix_crypto_symbol with filter)
SELECT symbol FROM crypto WHERE monitored = 1;
```

---

## Data Management Policies

### Data Retention

- **crypto**: Latest market data only (upserted on each collection)
- **account**: Current account state only (upserted on each collection)
- **holdings**: Current portfolio state only (replaced on each collection)
- **historical**: Permanent retention (incremental updates with duplicate prevention)

### Update Strategies

**Upsert (crypto, account):**
- Update existing records based on unique keys
- Insert new records if they don't exist
- Preserves historical create timestamps

**Replace (holdings):**
- Delete all existing records
- Insert fresh data
- Used because portfolio positions can change dramatically

**Incremental (historical):**
- Add new records only
- Skip duplicates using unique constraint
- Handles gaps in collection schedule automatically

### Data Integrity

**Constraints:**
- Primary keys on all tables
- Unique constraints on business keys (symbol, account_number)
- NOT NULL constraints on critical fields
- Default values where appropriate

**Validation:**
- Symbol format validation in application layer
- Price data validation (positive numbers)
- Timestamp validation and timezone handling

---

## Configuration and Customization

### Monitored Symbols

The `monitored` flag in the crypto table controls which symbols have historical data collected:

```sql
-- Enable monitoring for a symbol
UPDATE crypto SET monitored = 1 WHERE symbol = 'BTC-USD';

-- View monitored symbols
SELECT symbol FROM crypto WHERE monitored = 1;
```

### Historical Data Intervals

Historical data collection interval is configurable in `config.json`:

```json
{
  "historical_data": {
    "interval_minutes": 15,
    "days_back": 60,
    "buffer_days": 1
  }
}
```

---

## Storage and Maintenance

### File Location

Default database location: `crypto_trading.db` in the project root directory.
Configurable via `config.json`:

```json
{
  "database": {
    "path": "crypto_trading.db"
  }
}
```

### Backup Recommendations

1. **Regular backups** before running migrations or major updates
2. **File-based backups** using SQLite's built-in backup API
3. **Schema versioning** for future migrations

### Maintenance Tasks

**Regular:**
- Monitor database size growth (primarily from historical table)
- Verify data collection completeness
- Check for orphaned records

**Periodic:**
- Analyze query performance
- Update statistics for query optimization
- Consider archiving very old historical data if storage becomes an issue

---

## Tools and Scripts

### Management Scripts

- `add_monitored_column.py`: Database migration for monitored flag
- `set_monitored_flag.py`: Manage which symbols are monitored
- `view_candlestick_data.py`: Query and display historical data
- `candlestick_chart_viewer.py`: Create graphical charts from data

### Development Tools

- **SQLAlchemy ORM**: Object-relational mapping
- **Database browser**: Any SQLite browser (DB Browser for SQLite, etc.)
- **Migration support**: Built-in schema migration capabilities

---

## Performance Characteristics

### Expected Data Volumes

**Small Tables:**
- crypto: ~100-500 records (trading pairs)
- account: 1 record
- holdings: ~10-50 records (active positions)

**Large Table:**
- historical: Potentially millions of records
  - Per symbol: 35,040 records/year (15-min intervals)
  - 10 symbols × 1 year = ~350,000 records
  - Storage: ~50-100 MB per year for typical usage

### Query Performance

- **Symbol lookups**: Sub-millisecond (indexed)
- **Recent historical data**: Fast (optimized indexes)
- **Large date ranges**: Good performance with proper indexing
- **Cross-table joins**: Minimal (designed for independent table access)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Aug 2025 | Initial schema design |
| 1.1.0 | Aug 2025 | Added monitored column to crypto table |

---

*This document should be updated whenever schema changes are made to maintain accurate documentation.*