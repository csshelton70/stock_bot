#!/usr/bin/env python3
"""
Trading System Setup and Utilities
Provides setup, testing, and maintenance tools for the Multi-Timeframe RSI + MACD Trading System
"""

import os
import sys
import json
import sqlite3
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import argparse


def setup_logging():
    """Configure logging for setup utilities"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def check_dependencies() -> Dict[str, bool]:
    """Check if required dependencies are installed"""
    dependencies = {
        "pandas": False,
        "numpy": False,
        "talib": False,
        "sqlite3": True,  # Built-in
    }

    print("🔍 Checking dependencies...")

    for package, status in dependencies.items():
        if package == "sqlite3":
            continue

        try:
            if package == "talib":
                import talib
            else:
                __import__(package)
            dependencies[package] = True
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - Not installed")

    return dependencies


def install_dependencies():
    """Install missing dependencies"""
    print("\n📦 Installing dependencies...")

    # Standard packages
    packages = ["pandas", "numpy"]

    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + packages)
        print("✅ Standard packages installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing standard packages: {e}")
        return False

    # TA-Lib requires special handling
    print("\n🔧 Installing TA-Lib...")
    print("Note: TA-Lib may require system dependencies:")
    print("  Ubuntu/Debian: sudo apt-get install libta-lib-dev")
    print("  macOS: brew install ta-lib")
    print(
        "  Windows: pip install TA-Lib or use wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/"
    )

    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "TA-Lib"])
        print("✅ TA-Lib installed successfully")
    except subprocess.CalledProcessError:
        print(
            "⚠️  TA-Lib installation failed. You may need to install system dependencies first."
        )
        return False

    return True


def create_default_config(config_path: str = "trading_config.json"):
    """Create default configuration file"""
    config = {
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "alert_timeout_hours": 12,
        "normal_exit_window_hours": 2,
        "primary_symbols": [
            "BTC-USD",
            "ETH-USD",
            "ADA-USD",
            "SOL-USD",
            "MATIC-USD",
            "AVAX-USD",
            "DOT-USD",
            "LINK-USD",
        ],
        "database_path": "crypto_trading.db",
        "log_level": "INFO",
        "log_file": ".\\logs\\trading_system.log",
        "test_mode": False,
        "paper_trading": True,
        "robinhood": {"username": "", "password": ""},
    }

    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"✅ Created configuration file: {config_path}")
        return True
    except Exception as e:
        print(f"❌ Error creating config file: {e}")
        return False


def initialize_database(db_path: str = "crypto_trading.db"):
    """Initialize the trading system database"""
    print(f"🗄️  Initializing database: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create alert_states table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                initial_rsi REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX(symbol),
                INDEX(status),
                INDEX(start_time)
            )
        """
        )

        # Create system_log table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS system_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT,
                confidence TEXT,
                price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX(timestamp),
                INDEX(symbol),
                INDEX(event_type)
            )
        """
        )

        # Create trading_signals table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                confidence TEXT NOT NULL,
                price REAL NOT NULL,
                rsi_15min_value REAL,
                rsi_15min_trend TEXT,
                rsi_1hour_value REAL,
                rsi_1hour_trend TEXT,
                macd_line REAL,
                macd_signal_line REAL,
                macd_histogram REAL,
                macd_crossover TEXT,
                volume_trend TEXT,
                reasoning TEXT,
                alert_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX(symbol),
                INDEX(signal_type),
                INDEX(confidence),
                INDEX(created_at)
            )
        """
        )

        # Create performance tracking table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                entry_price REAL,
                exit_price REAL,
                profit_loss REAL,
                profit_loss_percent REAL,
                hold_duration_hours REAL,
                exit_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(signal_id) REFERENCES trading_signals(id)
            )
        """
        )

        conn.commit()
        conn.close()

        print("✅ Database initialized successfully")
        return True

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


def test_system():
    """Run basic system tests"""
    print("🧪 Running system tests...")

    # Test 1: Configuration loading
    try:
        if os.path.exists("trading_config.json"):
            with open("trading_config.json", "r") as f:
                config = json.load(f)
            print("  ✅ Configuration loading")
        else:
            print("  ⚠️  No configuration file found")
    except Exception as e:
        print(f"  ❌ Configuration loading failed: {e}")

    # Test 2: Database connectivity
    try:
        conn = sqlite3.connect("crypto_trading.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        if tables:
            print(f"  ✅ Database connectivity ({len(tables)} tables found)")
        else:
            print("  ⚠️  Database connected but no tables found")
    except Exception as e:
        print(f"  ❌ Database connectivity failed: {e}")

    # Test 3: Technical analysis functions
    try:
        import numpy as np
        import talib

        # Generate test data
        test_data = np.random.randn(50) * 0.02 + 1
        test_prices = np.cumprod(1 + test_data) * 100

        # Test RSI
        rsi = talib.RSI(test_prices)
        if not np.isnan(rsi[-1]):
            print("  ✅ RSI calculation")
        else:
            print("  ❌ RSI calculation failed")

        # Test MACD
        macd, signal, hist = talib.MACD(test_prices)
        if not np.isnan(macd[-1]):
            print("  ✅ MACD calculation")
        else:
            print("  ❌ MACD calculation failed")

    except Exception as e:
        print(f"  ❌ Technical analysis test failed: {e}")

    print("✅ System tests completed")


def cleanup_old_data(days_old: int = 30):
    """Clean up old log and alert data"""
    print(f"🧹 Cleaning up data older than {days_old} days...")

    try:
        conn = sqlite3.connect("crypto_trading.db")
        cursor = conn.cursor()

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        # Clean up old expired alerts
        cursor.execute(
            """
            DELETE FROM alert_states 
            WHERE status = 'expired' AND updated_at < ?
        """,
            (cutoff_date.isoformat(),),
        )

        expired_alerts_deleted = cursor.rowcount

        # Clean up old log entries
        cursor.execute(
            """
            DELETE FROM system_log 
            WHERE timestamp < ? AND event_type NOT IN ('SIGNAL_GENERATED_BUY', 'SIGNAL_GENERATED_SELL')
        """,
            (cutoff_date.isoformat(),),
        )

        log_entries_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        print(f"  ✅ Deleted {expired_alerts_deleted} expired alerts")
        print(f"  ✅ Deleted {log_entries_deleted} old log entries")

    except Exception as e:
        print(f"  ❌ Cleanup failed: {e}")


def show_system_status():
    """Display current system status"""
    print("📊 System Status Report")
    print("=" * 50)

    try:
        conn = sqlite3.connect("crypto_trading.db")
        cursor = conn.cursor()

        # Active alerts
        cursor.execute(
            """
            SELECT COUNT(*) FROM alert_states WHERE status = 'active'
        """
        )
        active_alerts = cursor.fetchone()[0]
        print(f"Active alerts: {active_alerts}")

        # Recent signals (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(hours=24)
        cursor.execute(
            """
            SELECT COUNT(*) FROM trading_signals 
            WHERE created_at > ?
        """,
            (yesterday.isoformat(),),
        )
        recent_signals = cursor.fetchone()[0]
        print(f"Signals (24h): {recent_signals}")

        # Signal breakdown by confidence
        cursor.execute(
            """
            SELECT confidence, COUNT(*) 
            FROM trading_signals 
            WHERE created_at > ?
            GROUP BY confidence
        """,
            (yesterday.isoformat(),),
        )

        confidence_breakdown = cursor.fetchall()
        if confidence_breakdown:
            print("Signal confidence breakdown (24h):")
            for confidence, count in confidence_breakdown:
                print(f"  {confidence}: {count}")

        # Most active symbols
        cursor.execute(
            """
            SELECT symbol, COUNT(*) as signal_count
            FROM trading_signals 
            WHERE created_at > ?
            GROUP BY symbol 
            ORDER BY signal_count DESC
            LIMIT 5
        """,
            ((datetime.utcnow() - timedelta(days=7)).isoformat(),),
        )

        active_symbols = cursor.fetchall()
        if active_symbols:
            print("Most active symbols (7 days):")
            for symbol, count in active_symbols:
                print(f"  {symbol}: {count} signals")

        conn.close()

    except Exception as e:
        print(f"❌ Error retrieving system status: {e}")


def backup_database():
    """Create database backup"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"crypto_trading_backup_{timestamp}.db"

        import shutil

        shutil.copy2("crypto_trading.db", backup_name)

        print(f"✅ Database backed up to: {backup_name}")
        return True
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False


def main():
    """Main setup utility function"""
    parser = argparse.ArgumentParser(description="Trading System Setup and Utilities")
    parser.add_argument("--setup", action="store_true", help="Run full setup")
    parser.add_argument("--check-deps", action="store_true", help="Check dependencies")
    parser.add_argument(
        "--install-deps", action="store_true", help="Install dependencies"
    )
    parser.add_argument("--init-db", action="store_true", help="Initialize database")
    parser.add_argument(
        "--create-config", action="store_true", help="Create default config"
    )
    parser.add_argument("--test", action="store_true", help="Run system tests")
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument(
        "--cleanup", type=int, metavar="DAYS", help="Clean up data older than DAYS"
    )
    parser.add_argument("--backup", action="store_true", help="Backup database")

    args = parser.parse_args()

    setup_logging()

    if args.setup:
        print("🚀 Running full system setup...")
        print("-" * 40)

        # Check and install dependencies
        deps = check_dependencies()
        if not all(deps.values()):
            if input("\nInstall missing dependencies? (y/n): ").lower() == "y":
                install_dependencies()

        # Create configuration
        if not os.path.exists("trading_config.json"):
            create_default_config()

        # Initialize database
        initialize_database()

        # Run tests
        test_system()

        print("\n✅ Setup completed!")
        print("📝 Next steps:")
        print("1. Edit trading_config.json with your settings")
        print("2. Add Robinhood API credentials if available")
        print("3. Run the trading system: python trading_system.py")

    elif args.check_deps:
        check_dependencies()

    elif args.install_deps:
        install_dependencies()

    elif args.init_db:
        initialize_database()

    elif args.create_config:
        create_default_config()

    elif args.test:
        test_system()

    elif args.status:
        show_system_status()

    elif args.cleanup:
        cleanup_old_data(args.cleanup)

    elif args.backup:
        backup_database()

    else:
        parser.print_help()
        print("\n💡 Quick start: python setup_utils.py --setup")


if __name__ == "__main__":
    main()
