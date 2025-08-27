"""
Interactive script for managing monitored cryptocurrency symbols
"""

import sys
import os
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connections import DatabaseManager
from data.repositories.crypto_repository import CryptoRepository
from config.settings import AppConfig


class MonitoredSymbolsManager:
    """Interactive manager for monitored symbols"""

    def __init__(self, config_path: str = "config.json"):
        self.config = AppConfig.load(config_path)
        self.db_manager = DatabaseManager(self.config.database.path)
        self.crypto_repo = CryptoRepository(self.db_manager)

    def show_current_status(self):
        """Show current monitoring status"""
        print("\n=== Current Crypto Symbols Status ===")

        try:
            from database import DatabaseSession
            from database.models import Crypto

            with DatabaseSession(self.db_manager) as session:
                all_cryptos = session.query(Crypto).order_by(Crypto.symbol).all()

                if not all_cryptos:
                    print("No crypto symbols found. Run data collector first.")
                    return

                monitored_count = 0
                print(f"\nFound {len(all_cryptos)} total symbols:")

                for crypto in all_cryptos:
                    status = "📈 MONITORED" if crypto.monitored else "   -"
                    price = f"${crypto.mid:,.2f}" if crypto.mid else "No price"
                    print(f"{status} | {crypto.symbol:12} | {price:>12}")

                    if crypto.monitored:
                        monitored_count += 1

                print(f"\nTotal monitored: {monitored_count}/{len(all_cryptos)}")

        except Exception as e:
            print(f"Error showing status: {e}")

    def set_monitored(self, symbols: List[str]) -> bool:
        """Set symbols as monitored"""
        try:
            updated_count = self.crypto_repo.set_monitored_status(
                symbols, monitored=True
            )
            print(f"✅ Set {updated_count} symbols as monitored")
            return updated_count > 0
        except Exception as e:
            print(f"❌ Error setting monitored: {e}")
            return False

    def unset_monitored(self, symbols: List[str]) -> bool:
        """Remove monitoring from symbols"""
        try:
            updated_count = self.crypto_repo.set_monitored_status(
                symbols, monitored=False
            )
            print(f"✅ Removed monitoring from {updated_count} symbols")
            return updated_count > 0
        except Exception as e:
            print(f"❌ Error removing monitoring: {e}")
            return False

    def set_all_monitored(self, monitored: bool = True) -> bool:
        """Set all symbols to monitored/unmonitored"""
        try:
            from database import DatabaseSession
            from database.models import Crypto

            with DatabaseSession(self.db_manager) as session:
                updated = session.query(Crypto).update({Crypto.monitored: monitored})

                action = "monitored" if monitored else "unmonitored"
                print(f"✅ Set {updated} symbols as {action}")
                return updated > 0

        except Exception as e:
            print(f"❌ Error setting all symbols: {e}")
            return False

    def interactive_menu(self):
        """Interactive menu for managing monitored symbols"""
        while True:
            print("\n" + "=" * 50)
            print("Monitored Symbols Manager")
            print("=" * 50)
            print("1. Show current status")
            print("2. Set symbols as monitored")
            print("3. Remove monitoring from symbols")
            print("4. Monitor all symbols")
            print("5. Stop monitoring all symbols")
            print("6. Quick setup (popular symbols)")
            print("7. Exit")

            choice = input("\nSelect option (1-7): ").strip()

            if choice == "1":
                self.show_current_status()

            elif choice == "2":
                symbols_input = input("Enter symbols (space-separated): ").strip()
                if symbols_input:
                    symbols = symbols_input.upper().split()
                    self.set_monitored(symbols)
                    self.show_current_status()

            elif choice == "3":
                symbols_input = input("Enter symbols to stop monitoring: ").strip()
                if symbols_input:
                    symbols = symbols_input.upper().split()
                    self.unset_monitored(symbols)
                    self.show_current_status()

            elif choice == "4":
                confirm = input("Monitor ALL symbols? (y/N): ").strip().lower()
                if confirm == "y":
                    self.set_all_monitored(True)
                    self.show_current_status()

            elif choice == "5":
                confirm = input("Stop monitoring ALL symbols? (y/N): ").strip().lower()
                if confirm == "y":
                    self.set_all_monitored(False)
                    self.show_current_status()

            elif choice == "6":
                popular_symbols = [
                    "BTC-USD",
                    "ETH-USD",
                    "ADA-USD",
                    "SOL-USD",
                    "MATIC-USD",
                    "DOT-USD",
                ]
                print(f"Setting popular symbols as monitored: {popular_symbols}")
                self.set_monitored(popular_symbols)
                self.show_current_status()

            elif choice == "7":
                print("Goodbye!")
                break

            else:
                print("Invalid option. Please try again.")
