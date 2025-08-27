# deployment_guide.md
"""
# Deployment Guide for Modular Robinhood Crypto App

## Pre-Deployment Steps

### 1. Backup Current System
```bash
# Run the migration script to backup existing files
python migrate_to_modular.py
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt

# If talib installation fails, install binary first:
# On Windows: Download from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
# On Ubuntu: sudo apt-get install libta-lib-dev
# On macOS: brew install ta-lib
```

### 3. Environment Setup
```bash
# Create environment variables file
cp .env.example .env

# Edit .env with your credentials
ROBINHOOD_API_KEY=your_api_key_here
ROBINHOOD_PRIVATE_KEY=your_private_key_here
DATABASE_PATH=crypto_trading.db
LOG_LEVEL=INFO
```

## Directory Structure Creation

```bash
# Create the modular directory structure
mkdir -p core config data/{repositories,models,migrations} trading/{analysis,strategies,alerts,execution} apps tests/{unit,integration} scripts logs

# Create __init__.py files
find . -type d -name "__pycache__" -prune -o -type d -exec touch {}/__init__.py \;
```

## File Migration

### 1. Copy Core Infrastructure
```bash
# Copy the refactored core files to appropriate directories
cp core_application_framework.py core/
cp config_settings.py config/settings.py
cp dependency_injection.py core/
cp error_handling.py core/
```

### 2. Copy Repository Layer
```bash
# Copy repository implementations
cp base_repository.py data/repositories/
cp crypto_repository.py data/repositories/
cp historical_repository.py data/repositories/
cp alert_repository.py data/repositories/
```

### 3. Copy Trading Components
```bash
# Copy trading system components
cp indicators.py trading/analysis/
cp base_strategy.py trading/strategies/
cp rsi_macd_strategy.py trading/strategies/
cp alert_manager.py trading/alerts/
```

### 4. Copy Applications
```bash
# Copy application entry points
cp data_collector_app.py apps/
cp trading_system_app.py apps/
```

### 5. Copy Scripts
```bash
# Copy runner scripts
cp run_collector.py scripts/
cp run_trading.py scripts/
chmod +x scripts/*.py
```

## Database Migration

### 1. Test Current Database
```bash
# Verify current database works
python -c "from database import DatabaseManager; db = DatabaseManager('crypto_trading.db'); print('Database OK')"
```

### 2. Run Trading System Migration (if needed)
```bash
# If you need trading system tables
python trading_migration.py --check
python trading_migration.py --backup --migrate
python trading_migration.py --verify
python trading_migration.py --set-monitored BTC-USD ETH-USD ADA-USD SOL-USD
```

## Testing the Migration

### 1. Test Data Collection
```bash
# Test new data collector
python scripts/run_collector.py

# Check logs for success
tail -f logs/app.log
```

### 2. Test Trading System
```bash
# Test new trading system
python scripts/run_trading.py

# Verify output
```

###