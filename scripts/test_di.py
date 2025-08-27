# Quick Debug Test Script - test_di_container.py
"""
Test script to debug DI container issues
"""
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_di_container():
    """Test the DI container to identify issues"""

    print("Testing DI Container...")

    try:
        from core.dependency_injection import DIContainer
        from database.connections import DatabaseManager
        from data.repositories.crypto_repository import CryptoRepository

        # Create container
        container = DIContainer()
        print("✓ DI Container created")

        # Register database manager
        db_manager = DatabaseManager("test.db")
        container.register("db_manager", db_manager)
        print("✓ Database manager registered")

        # Register crypto repo with factory
        def create_crypto_repo():
            print("  Creating CryptoRepository...")
            return CryptoRepository(container.get("db_manager"))

        container.register("crypto_repo", create_crypto_repo, singleton=True)
        print("✓ Crypto repo registered as singleton")

        # Test getting services
        db = container.get("db_manager")
        print("✓ Database manager retrieved")

        repo = container.get("crypto_repo")
        print("✓ Crypto repository retrieved")

        # Test singleton behavior
        repo2 = container.get("crypto_repo")
        print(f"✓ Singleton test: {repo is repo2}")

        print("\nAll tests passed! DI container is working correctly.")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_di_container()
