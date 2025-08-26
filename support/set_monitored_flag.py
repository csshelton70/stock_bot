#!/usr/bin/env python3
# ./set_monitored_flag.py
"""
Set Monitored Flag Script for Robinhood Crypto Trading App
=========================================================

This script allows you to manage the 'monitored' flag for crypto pairs in the database.
You can set individual crypto pairs to be monitored or not monitored, list current status,
or perform bulk operations.

Usage:
    python set_monitored_flag.py --crypto BTC-USD --true
    python set_monitored_flag.py --crypto ETH-USD --false
    python set_monitored_flag.py --list
    python set_monitored_flag.py --list-monitored
    python set_monitored_flag.py --list-unmonitored
    python set_monitored_flag.py --all --true
    python set_monitored_flag.py --holdings --true

Examples:
    # Set BTC-USD to be monitored
    python set_monitored_flag.py --crypto BTC-USD --true

    # Set multiple cryptos to not be monitored
    python set_monitored_flag.py --crypto BTC-USD,ETH-USD,ADA-USD --false

    # List all cryptos and their monitoring status
    python set_monitored_flag.py --list

    # Set all cryptos in holdings to be monitored
    python set_monitored_flag.py --holdings --true

    # Set all cryptos to not be monitored
    python set_monitored_flag.py --all --false

Author: Robinhood Crypto Trading App
Version: 1.0.0
"""
# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring


import sys
import os
import logging
import argparse
from typing import List, Optional

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.config import Config
from database import DatabaseManager, DatabaseSession
from database import Crypto, Holdings
from sqlalchemy import and_

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("set_monitored_flag")


class MonitoredFlagManager:
    """Manages the monitored flag for crypto pairs"""

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

    def validate_crypto_exists(self, session, symbol: str) -> bool:
        """Check if a crypto symbol exists in the database"""
        crypto = session.query(Crypto).filter_by(symbol=symbol.upper()).first()
        return crypto is not None

    def set_monitored_flag(self, symbols: List[str], monitored: bool) -> bool:
        """
        Set the monitored flag for specific crypto symbols

        Args:
            symbols: List of crypto symbols (e.g., ['BTC-USD', 'ETH-USD'])
            monitored: True to monitor, False to not monitor

        Returns:
            True if successful, False otherwise
        """
        try:
            with DatabaseSession(self.db_manager) as session:
                updated_count = 0
                not_found = []

                for symbol in symbols:
                    symbol = symbol.upper().strip()

                    # Check if crypto exists
                    crypto = session.query(Crypto).filter_by(symbol=symbol).first()

                    if crypto:
                        old_status = crypto.monitored
                        crypto.monitored = monitored
                        updated_count += 1

                        status_str = "monitored" if monitored else "not monitored"
                        old_status_str = "monitored" if old_status else "not monitored"

                        if old_status != monitored:
                            logger.info(f"✅ {symbol}: {old_status_str} → {status_str}")
                        else:
                            logger.info(f"ℹ️  {symbol}: already {status_str}")
                    else:
                        not_found.append(symbol)

                if not_found:
                    logger.warning(f"❌ Crypto pairs not found: {', '.join(not_found)}")

                if updated_count > 0:
                    action = "monitored" if monitored else "unmonitored"
                    logger.info(
                        f"📊 Updated {updated_count} crypto pairs to be {action}"
                    )
                    return True
                else:
                    logger.warning("No crypto pairs were updated")
                    return False

        except Exception as e:
            logger.error(f"Error setting monitored flag: {e}")
            return False

    def set_all_monitored_flag(self, monitored: bool) -> bool:
        """
        Set the monitored flag for ALL crypto pairs in the database

        Args:
            monitored: True to monitor all, False to not monitor any

        Returns:
            True if successful, False otherwise
        """
        try:
            with DatabaseSession(self.db_manager) as session:
                # Update all crypto records
                result = session.query(Crypto).update({Crypto.monitored: monitored})
                updated_count = result

                action = "monitored" if monitored else "unmonitored"
                logger.info(f"📊 Set ALL {updated_count} crypto pairs to be {action}")
                return True

        except Exception as e:
            logger.error(f"Error setting all monitored flags: {e}")
            return False

    def set_holdings_monitored_flag(self, monitored: bool) -> bool:
        """
        Set the monitored flag for crypto pairs that are currently in holdings

        Args:
            monitored: True to monitor, False to not monitor

        Returns:
            True if successful, False otherwise
        """
        try:
            with DatabaseSession(self.db_manager) as session:
                # Get all symbols from holdings with quantity > 0
                holdings = (
                    session.query(Holdings).filter(Holdings.total_quantity > 0).all()
                )

                if not holdings:
                    logger.warning("No holdings found")
                    return False

                symbols = [holding.symbol for holding in holdings]
                logger.info(f"Found {len(symbols)} symbols in holdings: {symbols}")

                return self.set_monitored_flag(symbols, monitored)

        except Exception as e:
            logger.error(f"Error setting holdings monitored flags: {e}")
            return False

    def list_crypto_status(self, filter_type: str = "all") -> bool:
        """
        List crypto pairs and their monitoring status

        Args:
            filter_type: "all", "monitored", or "unmonitored"

        Returns:
            True if successful, False otherwise
        """
        try:
            with DatabaseSession(self.db_manager) as session:
                # Build query based on filter
                query = session.query(Crypto).order_by(Crypto.symbol)

                if filter_type == "monitored":
                    query = query.filter(Crypto.monitored == True)
                elif filter_type == "unmonitored":
                    query = query.filter(Crypto.monitored == False)

                cryptos = query.all()

                if not cryptos:
                    logger.info(f"No crypto pairs found ({filter_type})")
                    return False

                # Display results
                print(f"\n📊 Crypto Pairs ({filter_type.upper()}):")
                print("=" * 60)
                print(f"{'Symbol':<15} {'Monitored':<12} {'Mid Price':<12} {'Updated'}")
                print("-" * 60)

                monitored_count = 0
                for crypto in cryptos:
                    status = "✅ Yes" if crypto.monitored else "❌ No"
                    mid_price = f"${crypto.mid:.6f}" if crypto.mid else "N/A"
                    updated = (
                        crypto.updated_at.strftime("%m/%d %H:%M")
                        if crypto.updated_at
                        else "N/A"
                    )

                    print(f"{crypto.symbol:<15} {status:<12} {mid_price:<12} {updated}")

                    if crypto.monitored:
                        monitored_count += 1

                print("-" * 60)
                print(f"Total: {len(cryptos)} pairs, {monitored_count} monitored")

                return True

        except Exception as e:
            logger.error(f"Error listing crypto status: {e}")
            return False

    def get_summary(self) -> dict:
        """Get summary statistics"""
        try:
            with DatabaseSession(self.db_manager) as session:
                total_cryptos = session.query(Crypto).count()
                monitored_cryptos = (
                    session.query(Crypto).filter(Crypto.monitored == True).count()
                )
                unmonitored_cryptos = total_cryptos - monitored_cryptos

                # Get holdings info
                total_holdings = (
                    session.query(Holdings).filter(Holdings.total_quantity > 0).count()
                )

                return {
                    "total_cryptos": total_cryptos,
                    "monitored": monitored_cryptos,
                    "unmonitored": unmonitored_cryptos,
                    "holdings": total_holdings,
                }
        except Exception as e:
            logger.error(f"Error getting summary: {e}")
            return {}

    def cleanup(self):
        """Cleanup database connections"""
        if hasattr(self, "db_manager"):
            self.db_manager.close()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Manage monitored flags for crypto pairs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python set_monitored_flag.py --crypto BTC-USD --true
  python set_monitored_flag.py --crypto BTC-USD,ETH-USD --false
  python set_monitored_flag.py --list
  python set_monitored_flag.py --holdings --true
  python set_monitored_flag.py --all --false
        """,
    )

    # Main action arguments
    parser.add_argument(
        "--crypto",
        type=str,
        help="Crypto symbol(s) - comma separated (e.g., BTC-USD,ETH-USD)",
    )
    parser.add_argument("--all", action="store_true", help="Apply to ALL crypto pairs")
    parser.add_argument(
        "--holdings", action="store_true", help="Apply to crypto pairs in holdings only"
    )

    # Flag setting arguments
    parser.add_argument(
        "--true",
        action="store_true",
        dest="monitored_true",
        help="Set monitored flag to True",
    )
    parser.add_argument(
        "--false",
        action="store_true",
        dest="monitored_false",
        help="Set monitored flag to False",
    )

    # Listing arguments
    parser.add_argument(
        "--list", action="store_true", help="List all crypto pairs and their status"
    )
    parser.add_argument(
        "--list-monitored", action="store_true", help="List only monitored crypto pairs"
    )
    parser.add_argument(
        "--list-unmonitored",
        action="store_true",
        help="List only unmonitored crypto pairs",
    )

    # Config
    parser.add_argument("--config", default="config.json", help="Config file path")

    args = parser.parse_args()

    # Validate arguments
    if not any(
        [
            args.crypto,
            args.all,
            args.holdings,
            args.list,
            args.list_monitored,
            args.list_unmonitored,
        ]
    ):
        parser.error(
            "Must specify one of: --crypto, --all, --holdings, --list, --list-monitored, --list-unmonitored"
        )

    if (args.crypto or args.all or args.holdings) and not (
        args.monitored_true or args.monitored_false
    ):
        parser.error("Must specify --true or --false when setting monitored flags")

    if args.monitored_true and args.monitored_false:
        parser.error("Cannot specify both --true and --false")

    manager = None
    try:
        logger.info("=== Monitored Flag Manager Starting ===")

        # Initialize manager
        manager = MonitoredFlagManager(args.config)

        # Show summary
        summary = manager.get_summary()
        if summary:
            logger.info(
                f"Database: {summary['total_cryptos']} cryptos, {summary['monitored']} monitored, {summary['holdings']} in holdings"
            )

        success = False

        # Handle listing commands
        if args.list:
            success = manager.list_crypto_status("all")
        elif args.list_monitored:
            success = manager.list_crypto_status("monitored")
        elif args.list_unmonitored:
            success = manager.list_crypto_status("unmonitored")

        # Handle setting commands
        elif args.crypto:
            symbols = [s.strip() for s in args.crypto.split(",")]
            monitored = args.monitored_true
            success = manager.set_monitored_flag(symbols, monitored)

        elif args.all:
            monitored = args.monitored_true
            success = manager.set_all_monitored_flag(monitored)

        elif args.holdings:
            monitored = args.monitored_true
            success = manager.set_holdings_monitored_flag(monitored)

        # Show final summary if changes were made
        if success and not any([args.list, args.list_monitored, args.list_unmonitored]):
            final_summary = manager.get_summary()
            if final_summary:
                logger.info(
                    f"Final status: {final_summary['monitored']}/{final_summary['total_cryptos']} cryptos monitored"
                )

        logger.info("=== Monitored Flag Manager Finished ===")
        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Operation failed with unexpected error: {e}")
        return 1

    finally:
        if manager:
            manager.cleanup()


if __name__ == "__main__":
    sys.exit(main())
