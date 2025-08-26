#!/usr/bin/env python3
# ./add_monitored_column.py

"""
Database Migration Script - Add 'monitored' Column to Crypto Table
================================================================

This script adds a boolean 'monitored' column to the crypto table and updates
the SQLAlchemy model. It handles the migration safely with rollback capability.

Usage:
    python add_monitored_column.py [--rollback]

Options:
    --rollback    Remove the monitored column (undo the migration)

Author: Robinhood Crypto Trading App
Version: 1.0.0
"""

import sys
import os
import logging
import argparse
from pathlib import Path

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, inspect
from utils import Config
from utils import setup_logging
from database import DatabaseManager, DatabaseSession

# Setup logging for migration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("migration")


class CryptoTableMigration:
    """Handles the migration of adding monitored column to crypto table"""

    def __init__(self, config_path: str = "config.json"):
        try:
            self.config = Config(config_path)
        except FileNotFoundError:
            # If config file not found, use default database path
            logger.warning(f"Config file not found, using default database path")
            self.db_path = "crypto_trading.db"
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.db_path = "crypto_trading.db"
        else:
            self.db_path = self.config.database_path

        self.db_manager = DatabaseManager(self.db_path)

    def check_column_exists(self) -> bool:
        """Check if the monitored column already exists"""
        try:
            inspector = inspect(self.db_manager.engine)
            columns = inspector.get_columns("crypto")

            for column in columns:
                if column["name"] == "monitored":
                    return True
            return False

        except Exception as e:
            logger.error(f"Error checking column existence: {e}")
            return False

    def backup_database(self) -> bool:
        """Create a backup of the database before migration"""
        try:
            backup_path = f"{self.db_path}.backup"

            # Copy the database file
            import shutil

            shutil.copy2(self.db_path, backup_path)

            logger.info(f"Database backed up to: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return False

    def add_monitored_column(self) -> bool:
        """Add the monitored column to the crypto table"""
        try:
            with DatabaseSession(self.db_manager) as session:
                # Check if column already exists
                if self.check_column_exists():
                    logger.warning("Column 'monitored' already exists in crypto table")
                    return True

                logger.info("Adding 'monitored' column to crypto table...")

                # Add the column with default value False
                session.execute(
                    text(
                        "ALTER TABLE crypto ADD COLUMN monitored BOOLEAN DEFAULT 0 NOT NULL"
                    )
                )

                logger.info("Column added successfully")

                # Update all existing records to set monitored = True
                # (assuming we want to monitor all existing crypto pairs)
                result = session.execute(text("UPDATE crypto SET monitored = 1"))

                updated_count = result.rowcount
                logger.info(
                    f"Updated {updated_count} existing records to monitored = True"
                )

                return True

        except Exception as e:
            logger.error(f"Failed to add monitored column: {e}")
            return False

    def remove_monitored_column(self) -> bool:
        """Remove the monitored column from the crypto table (rollback)"""
        try:
            with DatabaseSession(self.db_manager) as session:
                # Check if column exists
                if not self.check_column_exists():
                    logger.warning("Column 'monitored' does not exist in crypto table")
                    return True

                logger.info("Removing 'monitored' column from crypto table...")

                # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
                # First, get the existing data
                result = session.execute(
                    text(
                        """SELECT id, symbol, minimum_order, maximum_order, bid, mid, ask, 
                       created_at, updated_at FROM crypto"""
                    )
                )
                existing_data = result.fetchall()

                # Drop the table
                session.execute(text("DROP TABLE crypto"))

                # Recreate the table without monitored column
                session.execute(
                    text(
                        """
                    CREATE TABLE crypto (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol VARCHAR(20) UNIQUE NOT NULL,
                        minimum_order FLOAT,
                        maximum_order FLOAT,
                        bid FLOAT,
                        mid FLOAT,
                        ask FLOAT,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                """
                    )
                )

                # Create indexes
                session.execute(
                    text("CREATE INDEX ix_crypto_symbol ON crypto (symbol)")
                )

                # Reinsert the data
                for row in existing_data:
                    session.execute(
                        text(
                            """
                        INSERT INTO crypto (id, symbol, minimum_order, maximum_order, 
                                          bid, mid, ask, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                        ),
                        row,
                    )

                logger.info(
                    f"Recreated crypto table without monitored column, restored {len(existing_data)} records"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to remove monitored column: {e}")
            return False

    def verify_migration(self) -> bool:
        """Verify that the migration was successful"""
        try:
            with DatabaseSession(self.db_manager) as session:
                # Check if column exists and has correct type
                inspector = inspect(self.db_manager.engine)
                columns = inspector.get_columns("crypto")

                monitored_column = None
                for column in columns:
                    if column["name"] == "monitored":
                        monitored_column = column
                        break

                if monitored_column is None:
                    logger.error("Monitored column not found after migration")
                    return False

                # Check that it's a boolean type
                if "BOOLEAN" not in str(monitored_column["type"]).upper():
                    logger.warning(
                        f"Monitored column type is {monitored_column['type']}, expected BOOLEAN"
                    )

                # Check a few records
                result = session.execute(
                    text("SELECT symbol, monitored FROM crypto LIMIT 5")
                )
                sample_data = result.fetchall()

                logger.info("Migration verification:")
                logger.info(f"Column exists: Yes")
                logger.info(f"Column type: {monitored_column['type']}")
                logger.info(f"Sample data: {sample_data}")

                return True

        except Exception as e:
            logger.error(f"Failed to verify migration: {e}")
            return False

    def cleanup(self):
        """Cleanup database connections"""
        if hasattr(self, "db_manager"):
            self.db_manager.close()


def main():
    """Main migration function"""
    parser = argparse.ArgumentParser(description="Add monitored column to crypto table")
    parser.add_argument(
        "--rollback", action="store_true", help="Remove the monitored column"
    )
    parser.add_argument("--config", default="config.json", help="Config file path")

    args = parser.parse_args()

    migration = None
    try:
        logger.info("=== Crypto Table Migration Starting ===")

        # Initialize migration
        migration = CryptoTableMigration(args.config)

        if args.rollback:
            # Rollback migration
            logger.info("Rolling back migration (removing monitored column)...")

            # Backup database
            if not migration.backup_database():
                logger.error("Failed to backup database, aborting rollback")
                return 1

            # Remove column
            if not migration.remove_monitored_column():
                logger.error("Rollback failed")
                return 1

            logger.info("✅ Rollback completed successfully")

        else:
            # Apply migration
            logger.info("Applying migration (adding monitored column)...")

            # Backup database
            if not migration.backup_database():
                logger.error("Failed to backup database, aborting migration")
                return 1

            # Add column
            if not migration.add_monitored_column():
                logger.error("Migration failed")
                return 1

            # Verify migration
            if not migration.verify_migration():
                logger.error("Migration verification failed")
                return 1

            logger.info("✅ Migration completed successfully")

        logger.info("=== Migration Finished ===")
        return 0

    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Migration failed with unexpected error: {e}")
        return 1

    finally:
        if migration:
            migration.cleanup()


if __name__ == "__main__":
    sys.exit(main())
