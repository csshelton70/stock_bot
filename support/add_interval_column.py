#!/usr/bin/env python3
"""
Database Migration Script: Add interval_minutes support to historical table
===========================================================================

This script migrates the existing historical table to support multiple intervals.
It adds the interval_minutes column and updates the unique constraint.

IMPORTANT: This will modify your database structure. Make a backup before running!

Usage:
    python migrate_interval_support.py [--database-path path/to/db]
"""

import sys
import logging
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IntervalMigration:
    """Handles migration to add interval_minutes support"""

    def __init__(self, database_path: str):
        self.database_path = database_path
        self.backup_path = (
            f"{database_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

    def backup_database(self):
        """Create a backup of the database before migration"""
        try:
            logger.info(f"Creating backup: {self.backup_path}")

            # Read original database
            with open(self.database_path, "rb") as original:
                with open(self.backup_path, "wb") as backup:
                    backup.write(original.read())

            logger.info("Backup created successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False

    def check_migration_needed(self) -> bool:
        """Check if migration is needed"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()

            # Check if interval_minutes column exists
            cursor.execute("PRAGMA table_info(historical)")
            columns = [col[1] for col in cursor.fetchall()]

            has_interval_column = "interval_minutes" in columns
            conn.close()

            if has_interval_column:
                logger.info(
                    "Migration not needed - interval_minutes column already exists"
                )
                return False
            else:
                logger.info("Migration needed - interval_minutes column not found")
                return True

        except sqlite3.OperationalError as e:
            if "no such table: historical" in str(e):
                logger.info("No historical table found - migration not needed")
                return False
            else:
                raise

    def migrate_historical_table(self):
        """Migrate the historical table to support intervals"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()

            logger.info("Starting historical table migration...")

            # Begin transaction
            cursor.execute("BEGIN TRANSACTION")

            # Step 1: Create new table with interval support
            logger.info("Creating new historical table structure...")
            cursor.execute(
                """
                CREATE TABLE historical_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol VARCHAR(20) NOT NULL,
                    timestamp DATETIME NOT NULL,
                    interval_minutes INTEGER NOT NULL DEFAULT 15,
                    open FLOAT NOT NULL,
                    high FLOAT NOT NULL,
                    low FLOAT NOT NULL,
                    close FLOAT NOT NULL,
                    volume FLOAT DEFAULT 0.0,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uix_symbol_timestamp_interval UNIQUE (symbol, timestamp, interval_minutes)
                )
            """
            )

            # Step 2: Copy data from old table (assuming existing data is 15-minute intervals)
            logger.info("Copying existing data (assuming 15-minute intervals)...")
            cursor.execute(
                """
                INSERT INTO historical_new 
                (id, symbol, timestamp, interval_minutes, open, high, low, close, volume, created_at, updated_at)
                SELECT 
                    id, symbol, timestamp, 15 as interval_minutes, open, high, low, close, volume, created_at, updated_at
                FROM historical
            """
            )

            rows_copied = cursor.rowcount
            logger.info(f"Copied {rows_copied} existing records")

            # Step 3: Drop old table
            logger.info("Dropping old historical table...")
            cursor.execute("DROP TABLE historical")

            # Step 4: Rename new table
            logger.info("Renaming new table...")
            cursor.execute("ALTER TABLE historical_new RENAME TO historical")

            # Step 5: Create indexes
            logger.info("Creating indexes...")
            cursor.execute("CREATE INDEX ix_historical_symbol ON historical (symbol)")
            cursor.execute(
                "CREATE INDEX ix_historical_timestamp ON historical (timestamp)"
            )
            cursor.execute(
                "CREATE INDEX idx_historical_symbol_timestamp ON historical (symbol, timestamp)"
            )
            cursor.execute(
                "CREATE INDEX idx_historical_symbol_interval ON historical (symbol, interval_minutes)"
            )
            cursor.execute(
                "CREATE INDEX idx_historical_interval_timestamp ON historical (interval_minutes, timestamp)"
            )

            # Commit transaction
            cursor.execute("COMMIT")
            conn.close()

            logger.info("Migration completed successfully!")
            logger.info(f"Migrated {rows_copied} records")
            logger.info("All existing data has been marked as 15-minute intervals")

            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            try:
                cursor.execute("ROLLBACK")
                conn.close()
            except:
                pass
            return False

    def verify_migration(self):
        """Verify the migration was successful"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()

            # Check table structure
            cursor.execute("PRAGMA table_info(historical)")
            columns = {col[1]: col[2] for col in cursor.fetchall()}

            required_columns = {
                "id": "INTEGER",
                "symbol": "VARCHAR(20)",
                "timestamp": "DATETIME",
                "interval_minutes": "INTEGER",
                "open": "FLOAT",
                "high": "FLOAT",
                "low": "FLOAT",
                "close": "FLOAT",
                "volume": "FLOAT",
                "created_at": "DATETIME",
                "updated_at": "DATETIME",
            }

            missing_columns = []
            for col, col_type in required_columns.items():
                if col not in columns:
                    missing_columns.append(col)

            if missing_columns:
                logger.error(
                    f"Migration verification failed - missing columns: {missing_columns}"
                )
                return False

            # Check data integrity
            cursor.execute("SELECT COUNT(*) FROM historical")
            total_records = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM historical WHERE interval_minutes = 15"
            )
            interval_15_records = cursor.fetchone()[0]

            logger.info(f"Verification successful:")
            logger.info(f"  Total records: {total_records}")
            logger.info(f"  15-minute interval records: {interval_15_records}")

            # Check indexes
            cursor.execute("PRAGMA index_list(historical)")
            indexes = [idx[1] for idx in cursor.fetchall()]
            expected_indexes = [
                "ix_historical_symbol",
                "ix_historical_timestamp",
                "idx_historical_symbol_timestamp",
                "idx_historical_symbol_interval",
                "idx_historical_interval_timestamp",
            ]

            missing_indexes = [idx for idx in expected_indexes if idx not in indexes]
            if missing_indexes:
                logger.warning(f"Some indexes may be missing: {missing_indexes}")
            else:
                logger.info("All expected indexes are present")

            conn.close()
            return True

        except Exception as e:
            logger.error(f"Migration verification failed: {e}")
            return False

    def run_migration(self):
        """Run the complete migration process"""
        logger.info("=== Starting Database Migration for Interval Support ===")

        # Check if database exists
        if not Path(self.database_path).exists():
            logger.error(f"Database file not found: {self.database_path}")
            return False

        # Check if migration is needed
        if not self.check_migration_needed():
            logger.info("Migration not needed - database is already up to date")
            return True

        # Create backup
        if not self.backup_database():
            logger.error("Failed to create backup - aborting migration")
            return False

        # Run migration
        if not self.migrate_historical_table():
            logger.error("Migration failed")
            logger.info(f"Database backup available at: {self.backup_path}")
            return False

        # Verify migration
        if not self.verify_migration():
            logger.error("Migration verification failed")
            logger.info(f"Database backup available at: {self.backup_path}")
            return False

        logger.info("=== Migration Completed Successfully ===")
        logger.info(f"Backup saved at: {self.backup_path}")
        logger.info("Your database now supports multiple historical data intervals")

        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Migrate database to support multiple historical data intervals"
    )
    parser.add_argument(
        "--database-path",
        default="crypto_trading.db",
        help="Path to the database file (default: crypto_trading.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check if migration is needed without making changes",
    )

    args = parser.parse_args()

    migration = IntervalMigration(args.database_path)

    if args.dry_run:
        logger.info("=== Dry Run Mode ===")
        needed = migration.check_migration_needed()
        if needed:
            logger.info("Migration would be performed")
        else:
            logger.info("No migration needed")
        return 0

    success = migration.run_migration()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
