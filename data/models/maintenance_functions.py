# ./database/models.py
"""
SQLAlchemy models for Robinhood Crypto Trading App
ENHANCED: Strengthened unique constraints and validation for Historical table
"""
# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation, import-outside-toplevel

from typing import Dict, Any, List

from datetime import datetime

from historical import Historical   

from utils.logger import get_logger


logger = get_logger(__name__)


def create_missing_indexes(session) -> List[str]:
    """
    Create any missing indexes for optimal performance
    NEW FUNCTION: Ensures all performance indexes are present
    """
    try:
        from sqlalchemy import text

        created_indexes = []

        # Define critical indexes that should exist
        critical_indexes = [
            {
                "name": "idx_historical_symbol_timestamp_interval",
                "sql": "CREATE INDEX IF NOT EXISTS idx_historical_symbol_timestamp_interval ON historical(symbol, timestamp, interval_minutes)",
            },
            {
                "name": "idx_historical_timestamp_desc",
                "sql": "CREATE INDEX IF NOT EXISTS idx_historical_timestamp_desc ON historical(timestamp DESC)",
            },
            {
                "name": "idx_crypto_monitored",
                "sql": "CREATE INDEX IF NOT EXISTS idx_crypto_monitored ON crypto(monitored) WHERE monitored = 1",
            },
            {
                "name": "idx_alerts_active",
                "sql": "CREATE INDEX IF NOT EXISTS idx_alerts_active ON alert_states(status) WHERE status = 'active'",
            },
        ]

        for index_def in critical_indexes:
            try:
                session.execute(text(index_def["sql"]))
                created_indexes.append(index_def["name"])
            except Exception as e:
                get_logger(__name__).debug(
                    f"Index {index_def['name']} might already exist: {e}"
                )

        if created_indexes:
            session.commit()

        return created_indexes

    except Exception as e:
        get_logger(__name__).error(f"Error creating indexes: {e}")
        return []


def verify_database_constraints(session) -> Dict[str, Any]:
    """
    Verify that all database constraints are working properly
    NEW FUNCTION: Tests constraint enforcement
    """
    try:
        verification_results = {
            "constraints_tested": 0,
            "constraints_working": 0,
            "constraint_failures": [],
            "test_results": {},
        }

        # Test Historical table unique constraint
        try:
            from sqlalchemy.exc import IntegrityError

            # Try to insert duplicate historical record
            test_time = datetime.utcnow()
            duplicate_record = Historical(
                symbol="TEST-CONSTRAINT",
                timestamp=test_time,
                interval_minutes=15,
                open=100.0,
                high=100.0,
                low=100.0,
                close=100.0,
                volume=0.0,
            )

            # Insert first record
            session.add(duplicate_record)
            session.flush()

            # Try to insert duplicate - should fail
            duplicate_record2 = Historical(
                symbol="TEST-CONSTRAINT",
                timestamp=test_time,
                interval_minutes=15,
                open=101.0,  # Different values but same key
                high=101.0,
                low=101.0,
                close=101.0,
                volume=0.0,
            )

            session.add(duplicate_record2)

            try:
                session.flush()
                # If we get here, constraint is NOT working
                verification_results["constraint_failures"].append(
                    "Historical unique constraint NOT enforced"
                )
                verification_results["test_results"]["historical_unique"] = "FAILED"
            except IntegrityError:
                # Expected behavior - constraint is working
                session.rollback()
                verification_results["constraints_working"] += 1
                verification_results["test_results"]["historical_unique"] = "PASSED"

            verification_results["constraints_tested"] += 1

            # Clean up test data
            session.query(Historical).filter(
                Historical.symbol == "TEST-CONSTRAINT"
            ).delete()
            session.commit()

        except Exception as e:
            verification_results["constraint_failures"].append(
                f"Error testing historical constraint: {e}"
            )

        # Test check constraints (basic validation)
        try:
            # Test positive price constraint
            invalid_historical = Historical(
                symbol="TEST-CONSTRAINT-2",
                timestamp=datetime.utcnow(),
                interval_minutes=15,
                open=-100.0,  # Invalid negative price
                high=100.0,
                low=100.0,
                close=100.0,
                volume=0.0,
            )

            session.add(invalid_historical)

            try:
                session.flush()
                # If successful, check constraint is not working
                verification_results["constraint_failures"].append(
                    "Historical price check constraint NOT enforced"
                )
                verification_results["test_results"][
                    "historical_price_check"
                ] = "FAILED"

                # Clean up
                session.query(Historical).filter(
                    Historical.symbol == "TEST-CONSTRAINT-2"
                ).delete()

            except IntegrityError:  #type:ignore
                # Expected - constraint working
                session.rollback()
                verification_results["constraints_working"] += 1
                verification_results["test_results"][
                    "historical_price_check"
                ] = "PASSED"

            verification_results["constraints_tested"] += 1

        except Exception as e:
            verification_results["constraint_failures"].append(
                f"Error testing check constraint: {e}"
            )

        return verification_results

    except Exception as e:
        get_logger(__name__).error(f"Error verifying database constraints: {e}")
        return {
            "error": str(e),
            "constraints_tested": 0,
            "constraints_working": 0,
            "constraint_failures": [f"Constraint verification failed: {e}"],
            "test_results": {},
        }
