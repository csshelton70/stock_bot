#!/usr/bin/env python3
"""
Database Migration Script for Trading System
============================================

Migrates existing Robinhood crypto database to include new trading system tables.
Safely adds new tables without affecting existing data.

Author: Robinhood Crypto Trading System
Version: 1.0.0
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Import your existing database components
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
except ImportError as e:
    print(f"Error importing database models: {e}")
    print(
        "Make sure you've updated your models.py file with the new trading system tables"
    )
    sys.exit(1)

logger = logging.getLogger("database_migration")


class DatabaseMigration:
    """Handle database migration for trading system"""

    def __init__(self, db_path: str = "crypto_trading.db"):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.Session = sessionmaker(bind=self.engine)

        # Backup file path
        self.backup_path = (
            f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

    def backup_database(self) -> bool:
        """Create backup of existing database"""
        try:
            if not os.path.exists(self.db_path):
                logger.warning(f"Database file {self.db_path} does not exist")
                return False

            # Create backup using SQLite backup API
            source_conn = sqlite3.connect(self.db_path)
            backup_conn = sqlite3.connect(self.backup_path)

            source_conn.backup(backup_conn)

            source_conn.close()
            backup_conn.close()

            logger.info(f"Database backed up to: {self.backup_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False

    def check_existing_tables(self) -> dict:
        """Check which tables already exist"""
        try:
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()

            # Check for core tables
            core_tables = ["crypto", "account", "holdings", "historical"]
            trading_tables = [
                "alert_states",
                "system_log",
                "trading_signals",
                "technical_indicators",
                "signal_performance",
            ]

            status = {
                "core_tables": {
                    table: table in existing_tables for table in core_tables
                },
                "trading_tables": {
                    table: table in existing_tables for table in trading_tables
                },
                "all_existing": existing_tables,
            }

            return status

        except Exception as e:
            logger.error(f"Error checking existing tables: {e}")
            return {}

    def create_trading_tables(self) -> bool:
        """Create new trading system tables"""
        try:
            # Create only the trading system tables
            trading_tables = [
                AlertStates.__table__,
                SystemLog.__table__,
                TradingSignals.__table__,
                TechnicalIndicators.__table__,
                SignalPerformance.__table__,
            ]

            for table in trading_tables:
                try:
                    table.create(self.engine, checkfirst=True)
                    logger.info(f"Created table: {table.name}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.info(f"Table {table.name} already exists, skipping")
                    else:
                        logger.error(f"Error creating table {table.name}: {e}")
                        return False

            return True

        except Exception as e:
            logger.error(f"Error creating trading tables: {e}")
            return False

    def verify_table_structure(self) -> bool:
        """Verify that tables have correct structure"""
        try:
            with self.Session() as session:
                # Test basic operations on each table
                test_operations = [
                    ("alert_states", "SELECT COUNT(*) FROM alert_states"),
                    ("system_log", "SELECT COUNT(*) FROM system_log"),
                    ("trading_signals", "SELECT COUNT(*) FROM trading_signals"),
                    (
                        "technical_indicators",
                        "SELECT COUNT(*) FROM technical_indicators",
                    ),
                    ("signal_performance", "SELECT COUNT(*) FROM signal_performance"),
                ]

                for table_name, query in test_operations:
                    try:
                        result = session.execute(text(query)).scalar()
                        logger.info(f"Table {table_name}: {result} records")
                    except Exception as e:
                        logger.error(f"Error querying {table_name}: {e}")
                        return False

                return True

        except Exception as e:
            logger.error(f"Error verifying table structure: {e}")
            return False

    def add_sample_data(self) -> bool:
        """Add sample data for testing (optional)"""
        try:
            with self.Session() as session:
                # Add a sample system log entry
                sample_log = SystemLog(
                    symbol="BTC-USD",
                    event_type="SYSTEM_MIGRATION",
                    details="Trading system tables created successfully",
                    timestamp=datetime.utcnow(),
                )

                session.add(sample_log)
                session.commit()

                logger.info("Added sample data for testing")
                return True

        except Exception as e:
            logger.error(f"Error adding sample data: {e}")
            return False

    def run_migration(
        self, create_backup: bool = True, add_samples: bool = False
    ) -> bool:
        """Run complete migration process"""
        try:
            logger.info("=== Starting Database Migration ===")

            # Step 1: Check existing database
            if not os.path.exists(self.db_path):
                logger.error(f"Database file {self.db_path} not found!")
                logger.info(
                    "Please run your main data collection script first to create the database"
                )
                return False

            # Step 2: Check existing table status
            table_status = self.check_existing_tables()
            if not table_status:
                logger.error("Could not check existing tables")
                return False

            logger.info("Existing table status:")
            for table, exists in table_status["core_tables"].items():
                status = "✓" if exists else "✗"
                logger.info(f"  {table}: {status}")

            # Verify core tables exist
            missing_core = [
                table
                for table, exists in table_status["core_tables"].items()
                if not exists
            ]
            if missing_core:
                logger.error(f"Missing core tables: {missing_core}")
                logger.info("Please run your main data collection script first")
                return False

            # Step 3: Create backup
            if create_backup:
                logger.info("Creating database backup...")
                if not self.backup_database():
                    logger.error("Backup failed - aborting migration")
                    return False

            # Step 4: Create trading tables
            logger.info("Creating trading system tables...")
            if not self.create_trading_tables():
                logger.error("Failed to create trading tables")
                return False

            # Step 5: Verify table structure
            logger.info("Verifying table structure...")
            if not self.verify_table_structure():
                logger.error("Table structure verification failed")
                return False

            # Step 6: Add sample data (optional)
            if add_samples:
                logger.info("Adding sample data...")
                self.add_sample_data()

            # Step 7: Final verification
            final_status = self.check_existing_tables()
            trading_tables_created = sum(final_status["trading_tables"].values())

            logger.info("=== Migration Complete ===")
            logger.info(f"Trading tables created: {trading_tables_created}/5")

            if trading_tables_created == 5:
                logger.info("✓ All trading system tables created successfully!")
                logger.info("You can now run the trading system analysis")
                return True
            else:
                logger.warning(f"Only {trading_tables_created}/5 tables created")
                return False

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    def rollback_migration(self) -> bool:
        """Rollback migration by restoring backup"""
        try:
            if not os.path.exists(self.backup_path):
                logger.error(f"Backup file not found: {self.backup_path}")
                return False

            # Close any existing connections
            if hasattr(self, "engine"):
                self.engine.dispose()

            # Restore from backup
            import shutil

            shutil.copy2(self.backup_path, self.db_path)

            logger.info(f"Database restored from backup: {self.backup_path}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def generate_migration_report(self) -> str:
        """Generate migration status report"""
        try:
            report = []
            report.append("=" * 60)
            report.append("DATABASE MIGRATION REPORT")
            report.append("=" * 60)
            report.append(f"Database: {self.db_path}")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")

            # Check table status
            table_status = self.check_existing_tables()

            report.append("CORE TABLES STATUS")
            report.append("-" * 40)
            for table, exists in table_status["core_tables"].items():
                status = "✓ EXISTS" if exists else "✗ MISSING"
                report.append(f"  {table:<20} {status}")
            report.append("")

            report.append("TRADING SYSTEM TABLES STATUS")
            report.append("-" * 40)
            for table, exists in table_status["trading_tables"].items():
                status = "✓ EXISTS" if exists else "✗ MISSING"
                report.append(f"  {table:<20} {status}")
            report.append("")

            # Count records in each table
            if any(table_status["trading_tables"].values()):
                report.append("TABLE RECORD COUNTS")
                report.append("-" * 40)

                try:
                    with self.Session() as session:
                        for table_name in table_status["trading_tables"]:
                            if table_status["trading_tables"][table_name]:
                                try:
                                    count = session.execute(
                                        text(f"SELECT COUNT(*) FROM {table_name}")
                                    ).scalar()
                                    report.append(
                                        f"  {table_name:<20} {count:>10,} records"
                                    )
                                except:
                                    report.append(f"  {table_name:<20} {'ERROR':>10}")
                    report.append("")
                except:
                    report.append("  Error accessing database")
                    report.append("")

            # Migration status
            trading_tables_exist = sum(table_status["trading_tables"].values())
            core_tables_exist = sum(table_status["core_tables"].values())

            report.append("MIGRATION STATUS")
            report.append("-" * 40)

            if core_tables_exist == 4 and trading_tables_exist == 5:
                report.append("  Status: ✓ COMPLETE - Ready for trading system")
            elif core_tables_exist == 4 and trading_tables_exist > 0:
                report.append("  Status: ⚠ PARTIAL - Some trading tables missing")
            elif core_tables_exist == 4:
                report.append(
                    "  Status: ⚠ PENDING - Core tables exist, migration needed"
                )
            else:
                report.append("  Status: ✗ INCOMPLETE - Core tables missing")

            report.append(f"  Core tables: {core_tables_exist}/4")
            report.append(f"  Trading tables: {trading_tables_exist}/5")

            if hasattr(self, "backup_path") and os.path.exists(self.backup_path):
                report.append(f"  Backup available: {self.backup_path}")

            report.append("")
            report.append("=" * 60)

            return "\n".join(report)

        except Exception as e:
            return f"Error generating migration report: {e}"


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Database Migration for Trading System"
    )
    parser.add_argument("--db-path", default="crypto_trading.db", help="Database path")
    parser.add_argument("--migrate", action="store_true", help="Run migration")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    parser.add_argument("--add-samples", action="store_true", help="Add sample data")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--rollback", help="Rollback to backup file")
    parser.add_argument(
        "--report", action="store_true", help="Generate migration report"
    )
    parser.add_argument("--save-report", help="Save report to file")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("migration.log")],
    )

    try:
        migration = DatabaseMigration(args.db_path)

        if args.rollback:
            migration.backup_path = args.rollback
            success = migration.rollback_migration()
            if success:
                print("✓ Database rollback completed")
            else:
                print("✗ Database rollback failed")
                sys.exit(1)
            return

        if args.status or args.report:
            report = migration.generate_migration_report()

            if args.save_report:
                with open(args.save_report, "w") as f:
                    f.write(report)
                print(f"✓ Report saved to {args.save_report}")
            else:
                print(report)
            return

        if args.migrate:
            print("Starting database migration...")
            print("This will add trading system tables to your existing database")

            if not args.no_backup:
                confirm = (
                    input("Create backup before migration? (Y/n): ").lower().strip()
                )
                create_backup = confirm != "n"
            else:
                create_backup = False

            success = migration.run_migration(
                create_backup=create_backup, add_samples=args.add_samples
            )

            if success:
                print("\n✓ Migration completed successfully!")
                print("You can now run the trading system:")
                print("  python trading_system.py")
            else:
                print("\n✗ Migration failed!")
                if create_backup and os.path.exists(migration.backup_path):
                    print(f"Backup available at: {migration.backup_path}")
                    rollback = input("Rollback to backup? (y/N): ").lower().strip()
                    if rollback == "y":
                        migration.rollback_migration()
                sys.exit(1)
        else:
            # Show current status
            print("Database Migration Tool")
            print("Use --help for available options")
            print()

            table_status = migration.check_existing_tables()
            core_exists = (
                sum(table_status["core_tables"].values()) if table_status else 0
            )
            trading_exists = (
                sum(table_status["trading_tables"].values()) if table_status else 0
            )

            print(f"Core tables: {core_exists}/4")
            print(f"Trading tables: {trading_exists}/5")

            if core_exists == 4 and trading_exists == 0:
                print("\n⚠  Ready for migration - run with --migrate")
            elif core_exists == 4 and trading_exists == 5:
                print("\n✓  Migration complete - trading system ready")
            elif core_exists < 4:
                print("\n✗  Core tables missing - run main.py first")
            else:
                print(f"\n⚠  Partial migration - {5-trading_exists} tables missing")

    except Exception as e:
        logger.error(f"Migration tool error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

# Usage Examples:
"""
# Check current migration status
python database_migration.py --status

# Run migration with backup
python database_migration.py --migrate

# Run migration without backup
python database_migration.py --migrate --no-backup

# Generate detailed report
python database_migration.py --report --save-report migration_report.txt

# Rollback to backup
python database_migration.py --rollback crypto_trading.db.backup_20250824_143022

# Run migration with sample data
python database_migration.py --migrate --add-samples
"""
