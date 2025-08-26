#!/usr/bin/env python3
"""
Database Migration Script for Trading System
============================================

Migrates existing Robinhood crypto database to include new trading system tables.
Safely adds new tables and columns without affecting existing data.

Usage:
    python migration_script.py --backup --migrate
    python migration_script.py --check
    python migration_script.py --rollback
"""

import os
import sys
import sqlite3
import logging
import shutil
from datetime import datetime
from sqlalchemy import (
    create_engine,
    inspect,
    text,
    Column,
    String,
    Float,
    Integer,
    DateTime,
    Boolean,
    Index,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database import DatabaseManager
    from database.models import (
        Base,
        AlertStates,
        SystemLog,
        TradingSignals,
        TechnicalIndicators,
        SignalPerformance,
    )
    from database.connections import DatabaseSession
except ImportError as e:
    print(f"Error importing database models: {e}")
    print("Make sure your database modules are properly configured")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TradingSystemMigration:
    """Handle database migration for trading system integration"""

    def __init__(self, db_path: str = "crypto_trading.db"):
        self.db_path = db_path
        self.backup_path = (
            f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.Session = sessionmaker(bind=self.engine)

    def backup_database(self) -> bool:
        """Create backup of existing database"""
        try:
            if not os.path.exists(self.db_path):
                logger.warning(
                    f"Database file {self.db_path} does not exist, will be created fresh"
                )
                return True

            # Create backup using file copy
            shutil.copy2(self.db_path, self.backup_path)
            logger.info(f"Database backed up to: {self.backup_path}")
            return True

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

    def check_existing_schema(self) -> dict[str, list[str]]:
        """Check existing database schema"""
        inspector = inspect(self.engine)
        existing_tables = inspector.get_table_names()

        schema_info = {}
        for table_name in existing_tables:
            columns = inspector.get_columns(table_name)
            schema_info[table_name] = [col["name"] for col in columns]

        logger.info(f"Found {len(existing_tables)} existing tables: {existing_tables}")
        return schema_info

    def get_required_tables(self) -> dict[str, str]:
        """Define required trading system tables"""
        return {
            "alert_states": """
                CREATE TABLE IF NOT EXISTS alert_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol VARCHAR(20) NOT NULL,
                    alert_type VARCHAR(10) NOT NULL,
                    start_time DATETIME NOT NULL,
                    rsi_trigger_level FLOAT NOT NULL,
                    initial_rsi FLOAT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "system_log": """
                CREATE TABLE IF NOT EXISTS system_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    symbol VARCHAR(20) NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    details VARCHAR(1000),
                    confidence VARCHAR(10),
                    price FLOAT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "trading_signals": """
                CREATE TABLE IF NOT EXISTS trading_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol VARCHAR(20) NOT NULL,
                    signal_type VARCHAR(10) NOT NULL,
                    confidence VARCHAR(10) NOT NULL,
                    price FLOAT NOT NULL,
                    rsi_15min_value FLOAT,
                    rsi_15min_trend VARCHAR(20),
                    rsi_1hour_value FLOAT,
                    rsi_1hour_trend VARCHAR(20),
                    macd_line FLOAT,
                    macd_signal_line FLOAT,
                    macd_histogram FLOAT,
                    macd_crossover VARCHAR(20),
                    volume_trend VARCHAR(20),
                    reasoning TEXT,
                    alert_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "technical_indicators": """
                CREATE TABLE IF NOT EXISTS technical_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol VARCHAR(20) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    timestamp DATETIME NOT NULL,
                    rsi_14 FLOAT,
                    rsi_21 FLOAT,
                    macd_line FLOAT,
                    macd_signal FLOAT,
                    macd_histogram FLOAT,
                    sma_20 FLOAT,
                    sma_50 FLOAT,
                    ema_12 FLOAT,
                    ema_26 FLOAT,
                    bb_upper FLOAT,
                    bb_lower FLOAT,
                    bb_middle FLOAT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "signal_performance": """
                CREATE TABLE IF NOT EXISTS signal_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER,
                    symbol VARCHAR(20) NOT NULL,
                    signal_type VARCHAR(10) NOT NULL,
                    confidence VARCHAR(10) NOT NULL,
                    entry_price FLOAT NOT NULL,
                    current_price FLOAT,
                    exit_price FLOAT,
                    unrealized_pnl FLOAT,
                    realized_pnl FLOAT,
                    pnl_percent FLOAT,
                    max_profit FLOAT DEFAULT 0,
                    max_loss FLOAT DEFAULT 0,
                    hold_duration_hours FLOAT,
                    exit_reason VARCHAR(50),
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    performance_score FLOAT,
                    outcome VARCHAR(20),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """,
        }

    def get_required_indexes(self) -> dict[str, list[str]]:
        """Define required indexes for trading system tables"""
        return {
            "alert_states": [
                "CREATE INDEX IF NOT EXISTS idx_alert_symbol_status ON alert_states(symbol, status)",
                "CREATE INDEX IF NOT EXISTS idx_alert_start_time ON alert_states(start_time)",
                "CREATE INDEX IF NOT EXISTS idx_alert_type_status ON alert_states(alert_type, status)",
            ],
            "system_log": [
                "CREATE INDEX IF NOT EXISTS idx_log_timestamp ON system_log(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_log_symbol_event ON system_log(symbol, event_type)",
                "CREATE INDEX IF NOT EXISTS idx_log_event_type ON system_log(event_type)",
                "CREATE INDEX IF NOT EXISTS idx_log_confidence ON system_log(confidence)",
            ],
            "trading_signals": [
                "CREATE INDEX IF NOT EXISTS idx_signal_timestamp ON trading_signals(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_signal_symbol_type ON trading_signals(symbol, signal_type)",
                "CREATE INDEX IF NOT EXISTS idx_signal_confidence ON trading_signals(confidence)",
                "CREATE INDEX IF NOT EXISTS idx_signal_alert ON trading_signals(alert_id)",
            ],
            "technical_indicators": [
                "CREATE INDEX IF NOT EXISTS idx_tech_symbol_timeframe ON technical_indicators(symbol, timeframe)",
                "CREATE INDEX IF NOT EXISTS idx_tech_timestamp ON technical_indicators(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_tech_symbol_timestamp ON technical_indicators(symbol, timestamp)",
            ],
            "signal_performance": [
                "CREATE INDEX IF NOT EXISTS idx_perf_signal_id ON signal_performance(signal_id)",
                "CREATE INDEX IF NOT EXISTS idx_perf_symbol_outcome ON signal_performance(symbol, outcome)",
                "CREATE INDEX IF NOT EXISTS idx_perf_confidence_outcome ON signal_performance(confidence, outcome)",
                "CREATE INDEX IF NOT EXISTS idx_perf_active ON signal_performance(is_active)",
            ],
        }

    def add_crypto_monitoring_column(self) -> bool:
        """Add monitoring column to existing crypto table if it doesn't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check if crypto table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='crypto'"
                )
                if not cursor.fetchone():
                    logger.info(
                        "Crypto table doesn't exist yet, will be created by SQLAlchemy"
                    )
                    return True

                # Check if monitored column exists
                cursor.execute("PRAGMA table_info(crypto)")
                columns = [column[1] for column in cursor.fetchall()]

                if "monitored" not in columns:
                    logger.info("Adding 'monitored' column to crypto table")
                    cursor.execute(
                        "ALTER TABLE crypto ADD COLUMN monitored BOOLEAN DEFAULT FALSE"
                    )
                    conn.commit()
                    logger.info("Successfully added monitored column")
                else:
                    logger.info("Monitored column already exists in crypto table")

                return True

        except Exception as e:
            logger.error(f"Error adding monitored column: {e}")
            return False

    def migrate_trading_tables(self) -> bool:
        """Create trading system tables and indexes"""
        try:
            required_tables = self.get_required_tables()
            required_indexes = self.get_required_indexes()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create tables
                for table_name, create_sql in required_tables.items():
                    logger.info(f"Creating table: {table_name}")
                    cursor.execute(create_sql)

                # Create indexes
                for table_name, index_sqls in required_indexes.items():
                    for index_sql in index_sqls:
                        logger.info(f"Creating index for {table_name}")
                        cursor.execute(index_sql)

                conn.commit()
                logger.info(
                    "Successfully created all trading system tables and indexes"
                )
                return True

        except Exception as e:
            logger.error(f"Error creating trading tables: {e}")
            return False

    def verify_migration(self) -> bool:
        """Verify that migration was successful"""
        try:
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()

            required_table_names = list(self.get_required_tables().keys())

            missing_tables = []
            for table_name in required_table_names:
                if table_name not in existing_tables:
                    missing_tables.append(table_name)

            if missing_tables:
                logger.error(
                    f"Migration verification failed. Missing tables: {missing_tables}"
                )
                return False

            logger.info(
                "Migration verification successful - all required tables present"
            )
            return True

        except Exception as e:
            logger.error(f"Error verifying migration: {e}")
            return False

    def run_full_migration(self) -> bool:
        """Run complete migration process"""
        logger.info("Starting trading system database migration...")

        # Step 1: Backup
        if not self.backup_database():
            logger.error("Migration aborted - backup failed")
            return False

        try:
            # Step 2: Check existing schema
            existing_schema = self.check_existing_schema()

            # Step 3: Add monitoring column to crypto table
            if not self.add_crypto_monitoring_column():
                logger.error("Failed to add monitoring column")
                return False

            # Step 4: Create trading system tables
            if not self.migrate_trading_tables():
                logger.error("Failed to create trading system tables")
                return False

            # Step 5: Use SQLAlchemy to ensure all models are properly created
            logger.info("Running SQLAlchemy table creation...")
            Base.metadata.create_all(bind=self.engine)

            # Step 6: Verify migration
            if not self.verify_migration():
                logger.error("Migration verification failed")
                return False

            logger.info("✅ Migration completed successfully!")
            logger.info(f"Backup created at: {self.backup_path}")
            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            logger.info(f"You can restore from backup: {self.backup_path}")
            return False

    def rollback_migration(self) -> bool:
        """Rollback migration by restoring from backup"""
        if not os.path.exists(self.backup_path):
            logger.error("No backup file found for rollback")
            return False

        try:
            shutil.copy2(self.backup_path, self.db_path)
            logger.info("Migration rolled back successfully")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def set_monitored_symbols(self, symbols: list[str]) -> bool:
        """Set specific symbols as monitored in the crypto table"""
        try:
            with self.Session() as session:
                from database.models import Crypto

                # First, set all to not monitored
                session.query(Crypto).update({Crypto.monitored: False})

                # Then set specified symbols as monitored
                for symbol in symbols:
                    crypto = (
                        session.query(Crypto).filter(Crypto.symbol == symbol).first()
                    )
                    if crypto:
                        crypto.monitored = True
                        logger.info(f"Set {symbol} as monitored")
                    else:
                        # Create new crypto entry if it doesn't exist
                        new_crypto = Crypto(symbol=symbol, monitored=True)
                        session.add(new_crypto)
                        logger.info(f"Created new crypto entry for {symbol}")

                session.commit()
                logger.info(f"Successfully set {len(symbols)} symbols as monitored")
                return True

        except Exception as e:
            logger.error(f"Error setting monitored symbols: {e}")
            return False


def main():
    """Main migration script"""
    import argparse

    parser = argparse.ArgumentParser(description="Trading System Database Migration")
    parser.add_argument(
        "--db-path", default="crypto_trading.db", help="Database file path"
    )
    parser.add_argument(
        "--backup", action="store_true", help="Create backup before migration"
    )
    parser.add_argument("--migrate", action="store_true", help="Run migration")
    parser.add_argument("--check", action="store_true", help="Check existing schema")
    parser.add_argument("--verify", action="store_true", help="Verify migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")
    parser.add_argument(
        "--set-monitored", nargs="+", help="Set symbols as monitored", metavar="SYMBOL"
    )

    args = parser.parse_args()

    migration = TradingSystemMigration(args.db_path)

    if args.check:
        schema = migration.check_existing_schema()
        print("\nExisting Database Schema:")
        for table, columns in schema.items():
            print(f"  {table}: {', '.join(columns)}")

    elif args.backup:
        if migration.backup_database():
            print(f"✅ Backup created: {migration.backup_path}")
        else:
            print("❌ Backup failed")

    elif args.migrate:
        if migration.run_full_migration():
            print("✅ Migration completed successfully!")
        else:
            print("❌ Migration failed")

    elif args.verify:
        if migration.verify_migration():
            print("✅ Migration verification successful")
        else:
            print("❌ Migration verification failed")

    elif args.rollback:
        if migration.rollback_migration():
            print("✅ Migration rolled back")
        else:
            print("❌ Rollback failed")

    elif args.set_monitored:
        if migration.set_monitored_symbols(args.set_monitored):
            print(f"✅ Set {len(args.set_monitored)} symbols as monitored")
        else:
            print("❌ Failed to set monitored symbols")

    else:
        print("Trading System Database Migration")
        print("Available operations:")
        print("  --check              Check existing schema")
        print("  --backup             Create database backup")
        print("  --migrate            Run full migration")
        print("  --verify             Verify migration success")
        print("  --rollback           Rollback to backup")
        print("  --set-monitored SYM  Set symbols as monitored")
        print("\nRecommended sequence:")
        print("  1. python migration_script.py --check")
        print("  2. python migration_script.py --backup --migrate")
        print("  3. python migration_script.py --verify")
        print(
            "  4. python migration_script.py --set-monitored BTC-USD ETH-USD ADA-USD SOL-USD"
        )


if __name__ == "__main__":
    main()
