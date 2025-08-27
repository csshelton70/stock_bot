#!/usr/bin/env python3
"""
Duplicate Records Fix Migration Script
Fixes any existing duplicate records and ensures database integrity
"""

import sys
import os
import sqlite3
import shutil
from datetime import datetime

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connections import DatabaseManager
from database import DatabaseSession
from database.operations import DatabaseOperations


class DuplicateFixMigration:
    """Migration to fix duplicate records and strengthen constraints"""

    def __init__(self, db_path: str = "crypto_trading.db"):
        self.db_path = db_path
        self.backup_path = (
            f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

    def run_migration(self) -> bool:
        """Run complete duplicate fix migration"""

        print("🔧 Running Duplicate Records Fix Migration")
        print("=" * 50)

        try:
            # Step 1: Backup database
            if not self._backup_database():
                return False

            # Step 2: Analyze current state
            if not self._analyze_current_state():
                return False

            # Step 3: Fix duplicates
            if not self._fix_duplicate_records():
                return False

            # Step 4: Verify constraints
            if not self._verify_constraints():
                return False

            # Step 5: Final validation
            if not self._final_validation():
                return False

            print("✅ Migration completed successfully!")
            print(f"📁 Original database backed up to: {self.backup_path}")
            return True

        except Exception as e:
            print(f"❌ Migration failed: {e}")
            self._restore_from_backup()
            return False

    def _backup_database(self) -> bool:
        """Create backup of current database"""
        try:
            if not os.path.exists(self.db_path):
                print(f"❌ Database file not found: {self.db_path}")
                return False

            print(f"📋 Creating backup: {self.backup_path}")
            shutil.copy2(self.db_path, self.backup_path)

            # Verify backup
            if os.path.exists(self.backup_path):
                backup_size = os.path.getsize(self.backup_path)
                original_size = os.path.getsize(self.db_path)

                if backup_size == original_size:
                    print(f"✅ Backup created successfully ({backup_size:,} bytes)")
                    return True
                else:
                    print(f"❌ Backup size mismatch: {backup_size} vs {original_size}")
                    return False
            else:
                print("❌ Backup file was not created")
                return False

        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False

    def _analyze_current_state(self) -> bool:
        """Analyze current database state"""
        try:
            print("\n🔍 Analyzing current database state...")

            db_manager = DatabaseManager(self.db_path)

            with DatabaseSession(db_manager) as session:
                # Get duplicate summary
                duplicate_summary = DatabaseOperations.get_duplicate_detection_summary(
                    session
                )

                total_records = duplicate_summary.get("symbol_statistics", [])
                total_count = sum(stat["total_records"] for stat in total_records)
                duplicate_count = duplicate_summary.get("duplicate_records", 0)

                print(f"📊 Current State Analysis:")
                print(f"   Total historical records: {total_count:,}")
                print(f"   Duplicate record sets: {duplicate_count}")

                if duplicate_count > 0:
                    print(f"   ⚠️  Found {duplicate_count} sets of duplicate records")

                    # Show some examples
                    dup_details = duplicate_summary.get("duplicate_details", [])
                    for i, dup in enumerate(dup_details[:5]):
                        print(
                            f"      {dup['symbol']} @ {dup['timestamp']}: {dup['count']} copies"
                        )

                    if len(dup_details) > 5:
                        print(f"      ... and {len(dup_details) - 5} more")
                else:
                    print("   ✅ No duplicate records found")

                return True

        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            return False

    def _fix_duplicate_records(self) -> bool:
        """Fix duplicate records in the database"""
        try:
            print("\n🛠️  Fixing duplicate records...")

            db_manager = DatabaseManager(self.db_path)

            with DatabaseSession(db_manager) as session:
                # Clean up duplicates
                cleaned_count = DatabaseOperations.cleanup_duplicate_records(session)

                if cleaned_count > 0:
                    print(f"✅ Removed {cleaned_count} duplicate records")
                else:
                    print("✅ No duplicate records found to clean")

                return True

        except Exception as e:
            print(f"❌ Duplicate cleanup failed: {e}")
            return False

    def _verify_constraints(self) -> bool:
        """Verify that database constraints are working"""
        try:
            print("\n🔒 Verifying database constraints...")

            db_manager = DatabaseManager(self.db_path)

            with DatabaseSession(db_manager) as session:
                # Import the enhanced models to ensure constraints are applied
                from database.models import verify_database_constraints

                constraint_results = verify_database_constraints(session)

                tested = constraint_results.get("constraints_tested", 0)
                working = constraint_results.get("constraints_working", 0)
                failures = constraint_results.get("constraint_failures", [])

                print(f"📋 Constraint Verification Results:")
                print(f"   Constraints tested: {tested}")
                print(f"   Constraints working: {working}")

                if failures:
                    print("   ❌ Constraint failures:")
                    for failure in failures:
                        print(f"      - {failure}")
                    return False
                else:
                    print("   ✅ All constraints working properly")

                # Test duplicate prevention specifically
                return self._test_duplicate_prevention(session)

        except Exception as e:
            print(f"❌ Constraint verification failed: {e}")
            return False

    def _test_duplicate_prevention(self, session) -> bool:
        """Test that duplicate prevention is working"""
        try:
            print("🧪 Testing duplicate prevention...")

            # Create test record
            test_timestamp = datetime.utcnow()

            from database.models import Historical

            test_record = Historical(
                symbol="TEST-DUP-PREVENTION",
                timestamp=test_timestamp,
                interval_minutes=15,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=1000.0,
            )

            # Insert first record
            session.add(test_record)
            session.flush()

            # Try to insert duplicate
            duplicate_record = Historical(
                symbol="TEST-DUP-PREVENTION",
                timestamp=test_timestamp,
                interval_minutes=15,
                open=101.0,  # Different values but same unique key
                high=106.0,
                low=96.0,
                close=103.0,
                volume=1001.0,
            )

            session.add(duplicate_record)

            try:
                session.flush()
                # If we get here, duplicate prevention failed
                print("❌ Duplicate prevention test FAILED - duplicate was inserted")

                # Clean up
                session.query(Historical).filter(
                    Historical.symbol == "TEST-DUP-PREVENTION"
                ).delete()
                session.commit()
                return False

            except Exception:
                # Expected - duplicate was prevented
                session.rollback()
                print("✅ Duplicate prevention test PASSED")

                # Clean up the original test record
                session.query(Historical).filter(
                    Historical.symbol == "TEST-DUP-PREVENTION"
                ).delete()
                session.commit()
                return True

        except Exception as e:
            print(f"❌ Duplicate prevention test error: {e}")
            return False

    def _final_validation(self) -> bool:
        """Final validation of migration success"""
        try:
            print("\n✅ Running final validation...")

            db_manager = DatabaseManager(self.db_path)

            with DatabaseSession(db_manager) as session:
                # Check for any remaining duplicates
                duplicate_summary = DatabaseOperations.get_duplicate_detection_summary(
                    session
                )
                remaining_duplicates = duplicate_summary.get("duplicate_records", 0)

                if remaining_duplicates > 0:
                    print(
                        f"❌ Final validation failed: {remaining_duplicates} duplicate sets remain"
                    )
                    return False

                # Get final statistics
                integrity_report = (
                    DatabaseOperations.validate_database_integrity_comprehensive(
                        session
                    )
                )

                print("📊 Final Database State:")
                stats = integrity_report.get("statistics", {})
                print(
                    f"   Total historical records: {stats.get('total_historical_records', 0):,}"
                )
                print(f"   Monitored symbols: {stats.get('monitored_symbols', 0)}")
                print(
                    f"   Database status: {integrity_report.get('status', 'unknown')}"
                )

                # Check issues
                issues = integrity_report.get("issues", [])
                warnings = integrity_report.get("warnings", [])

                if issues:
                    print("❌ Final validation issues:")
                    for issue in issues:
                        print(f"      - {issue}")
                    return False

                if warnings:
                    print("⚠️  Final validation warnings:")
                    for warning in warnings:
                        print(f"      - {warning}")

                print("✅ Final validation passed!")
                return True

        except Exception as e:
            print(f"❌ Final validation error: {e}")
            return False

    def _restore_from_backup(self) -> bool:
        """Restore database from backup if migration fails"""
        try:
            if os.path.exists(self.backup_path):
                print(f"🔄 Restoring from backup: {self.backup_path}")
                shutil.copy2(self.backup_path, self.db_path)
                print("✅ Database restored from backup")
                return True
            else:
                print("❌ Backup file not found for restoration")
                return False
        except Exception as e:
            print(f"❌ Restoration failed: {e}")
            return False

    def verify_migration_success(self) -> bool:
        """Verify that migration was successful"""
        try:
            db_manager = DatabaseManager(self.db_path)

            with DatabaseSession(db_manager) as session:
                # Check for duplicates
                duplicate_summary = DatabaseOperations.get_duplicate_detection_summary(
                    session
                )
                duplicates = duplicate_summary.get("duplicate_records", 0)

                # Verify constraints are working
                from database.models import verify_database_constraints

                constraint_results = verify_database_constraints(session)
                working_constraints = constraint_results.get("constraints_working", 0)
                constraint_failures = constraint_results.get("constraint_failures", [])

                print(f"\n📋 Migration Verification Results:")
                print(f"   Duplicate records: {duplicates}")
                print(f"   Working constraints: {working_constraints}")

                if constraint_failures:
                    print(f"   Constraint issues: {len(constraint_failures)}")
                    for failure in constraint_failures:
                        print(f"      - {failure}")

                success = duplicates == 0 and len(constraint_failures) == 0

                if success:
                    print("✅ Migration verification PASSED")
                else:
                    print("❌ Migration verification FAILED")

                return success

        except Exception as e:
            print(f"❌ Migration verification error: {e}")
            return False


def main():
    """Main migration entry point"""

    print("🏦 Robinhood Crypto Database Duplicate Fix Migration")
    print("=" * 60)

    db_path = "crypto_trading.db"

    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        print("   Create the database first by running the data collector")
        return 1

    migration = DuplicateFixMigration(db_path)

    # Ask for confirmation
    print(f"📁 Target database: {db_path}")
    print(f"💾 Backup will be created: {migration.backup_path}")
    print()

    confirm = input("Proceed with migration? (y/N): ").strip().lower()
    if confirm != "y":
        print("Migration cancelled by user")
        return 0

    # Run migration
    if migration.run_migration():
        print("\n🎉 Migration completed successfully!")

        # Offer to verify
        verify = input("Run verification check? (Y/n): ").strip().lower()
        if verify != "n":
            if migration.verify_migration_success():
                print("🎯 All checks passed! Database is ready.")
            else:
                print("⚠️  Some verification checks failed. Check logs for details.")

        return 0
    else:
        print("\n❌ Migration failed. Database may have been restored from backup.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
