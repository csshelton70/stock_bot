# Test script for the refactored historical collector
# test_historical_collector.py
"""
Test script for the refactored historical collector
"""
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_historical_collector():
    """Test the refactored historical collector"""

    print("Testing Refactored Historical Collector...")

    try:
        from database.connections import DatabaseManager
        from data.repositories.historical_repository import HistoricalRepository
        from data.repositories.crypto_repository import CryptoRepository
        from collectors.historical_collector import HistoricalCollector
        from utils.retry import RetryConfig

        # Setup
        db_manager = DatabaseManager("test.db")
        db_manager.create_tables()

        historical_repo = HistoricalRepository(db_manager)
        crypto_repo = CryptoRepository(db_manager)
        retry_config = RetryConfig()

        print("✓ Repositories created")

        # Add a test monitored symbol
        from database.models import Crypto
        from database import DatabaseSession

        with DatabaseSession(db_manager) as session:
            test_crypto = Crypto(symbol="BTC-USD", monitored=True)
            session.add(test_crypto)

        print("✓ Test symbol added")

        # Create collector
        collector = HistoricalCollector(
            db_manager=db_manager,
            retry_config=retry_config,
            historical_repo=historical_repo,
            crypto_repo=crypto_repo,
            days_back=1,  # Small test
            interval_minutes=60,
            buffer_days=1,
        )

        print("✓ Historical collector created")
        print(f"✓ Collector name: {collector.get_collector_name()}")

        # Test data collection (this will make real API calls)
        print("Testing data collection (this may take a moment)...")
        success = collector.collect_and_store()

        if success:
            print("✓ Data collection successful!")

            # Check what was collected
            with DatabaseSession(db_manager) as session:
                from database.models import Historical

                count = session.query(Historical).count()
                print(f"✓ {count} historical records in database")
        else:
            print("✗ Data collection failed")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_historical_collector()
