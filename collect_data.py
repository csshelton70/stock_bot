#!/usr/bin/env python3
"""
Robinhood Crypto Trading App - Main Data Collection Script
=========================================================

This script collects cryptocurrency trading data from Robinhood and stores it in SQLite database.
Designed to be run via cron (Linux) or Task Scheduler (Windows).

Data collected:
- Cryptocurrency pairs and current prices
- Account information
- Portfolio holdings
- Historical price data (from Coinbase API) - 15min and 60min intervals

Author: Robinhood Crypto Trading App
"""
# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring


import sys

# import os
import logging
from typing import List, Tuple

# Add project root to Python path
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta

from sqlalchemy import text

from utils import Config
from utils import setup_logging
from utils import RetryConfig
from collectors import CryptoCollector
from collectors import AccountCollector
from collectors import HoldingsCollector
from collectors import HistoricalCollector
from database import DatabaseSession, DatabaseManager
from database import Historical


logger = logging.getLogger("robinhood_crypto_app.main")


class RobinhoodDataCollector:
    """Main application class for collecting Robinhood data"""

    def __init__(self, config_path: str = "config.json"):
        self.config = Config(config_path)
        self.db_manager = None
        self.retry_config = None
        self._setup()

    def _setup(self):
        """Setup application components"""
        # Validate configuration
        self.config.validate()

        # Setup logging
        setup_logging(self.config)
        logger.info("=== Robinhood Crypto Data Collector Starting ===")

        # Setup retry configuration
        self.retry_config = RetryConfig(
            max_attempts=self.config.retry_max_attempts,
            backoff_factor=self.config.retry_backoff_factor,
            initial_delay=self.config.retry_initial_delay,
        )

        # Setup database
        self.db_manager = DatabaseManager(self.config.database_path)
        self.db_manager.create_tables()

        logger.info("Application setup completed successfully")

    def cleanup_old_historical_data(self) -> bool:
        """
        Delete historical data older than days_back configuration and vacuum database

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("--- Cleaning Up Old Historical Data ---")

            # Calculate cutoff date based on days_back configuration
            cutoff_date = datetime.now() - timedelta(
                days=self.config.historical_days_back
            )
            logger.info(
                f"Removing historical data older than {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            with DatabaseSession(self.db_manager) as session:
                # Count records that will be deleted (for logging)
                old_records_count = (
                    session.query(Historical)
                    .filter(Historical.timestamp < cutoff_date)
                    .count()
                )

                if old_records_count == 0:
                    logger.info("No old historical data found to clean up")
                    return True

                logger.info(f"Found {old_records_count} historical records to delete")

                # Delete old records
                deleted_count = (
                    session.query(Historical)
                    .filter(Historical.timestamp < cutoff_date)
                    .delete(synchronize_session=False)
                )

                # Commit the deletion
                session.flush()

                logger.info(
                    f"Successfully deleted {deleted_count} old historical records"
                )

                session.commit()
                # Log remaining record count
                remaining_count = session.query(Historical).count()
                logger.info(f"Remaining historical records: {remaining_count}")

                # Run VACUUM to reclaim disk space
                logger.info("Running database VACUUM to reclaim disk space...")
                session.execute(text("VACUUM"))
                logger.info("Database VACUUM completed - disk space reclaimed")

                return True

        except Exception as e:
            logger.error(f"Failed to cleanup old historical data: {e}")
            return False

    def _collect_crypto_data(self) -> bool:
        """Collect cryptocurrency pairs and prices"""
        try:
            logger.info("--- Collecting Crypto Data ---")
            collector = CryptoCollector(
                self.retry_config,
                self.config.robinhood_api_key,
                self.config.robinhood_private_key_base64,
            )
            return collector.collect_and_store(self.db_manager)
        except Exception as e:
            logger.error(f"Crypto data collection failed: {e}")
            return False

    def _collect_account_data(self) -> bool:
        """Collect account information"""
        try:
            logger.info("--- Collecting Account Data ---")
            collector = AccountCollector(
                self.retry_config,
                self.config.robinhood_api_key,
                self.config.robinhood_private_key_base64,
            )
            return collector.collect_and_store(self.db_manager)
        except Exception as e:
            logger.error(f"Account data collection failed: {e}")
            return False

    def _collect_holdings_data(self) -> bool:
        """Collect holdings information"""
        try:
            logger.info("--- Collecting Holdings Data ---")
            collector = HoldingsCollector(
                self.retry_config,
                self.config.robinhood_api_key,
                self.config.robinhood_private_key_base64,
            )
            return collector.collect_and_store(self.db_manager)
        except Exception as e:
            logger.error(f"Holdings data collection failed: {e}")
            return False

    def _collect_historical_data_15min(self) -> bool:
        """Collect 15-minute interval historical price data from Coinbase"""
        try:
            logger.info("--- Collecting Historical Data (15min intervals) ---")
            collector = HistoricalCollector(
                retry_config=self.retry_config,
                days_back=self.config.historical_days_back,
                interval_minutes=15,  # Fixed to 15 minutes
                buffer_days=self.config.historical_buffer_days,
            )
            return collector.collect_and_store(self.db_manager)

        except Exception as e:
            logger.error(f"15-minute historical data collection failed: {e}")
            return False

    def _collect_historical_data_60min(self) -> bool:
        """Collect 60-minute interval historical price data from Coinbase"""
        try:
            logger.info("--- Collecting Historical Data (60min intervals) ---")
            collector = HistoricalCollector(
                retry_config=self.retry_config,
                days_back=self.config.historical_days_back,
                interval_minutes=60,  # Fixed to 60 minutes
                buffer_days=self.config.historical_buffer_days,
            )
            return collector.collect_and_store(self.db_manager)

        except Exception as e:
            logger.error(f"60-minute historical data collection failed: {e}")
            return False

    def run_data_collection(self) -> Tuple[bool, List[str]]:
        """
        Run the complete data collection process

        Returns:
            Tuple of (overall_success, list_of_failed_collections)
        """
        failed_collections = []

        try:
            # Collect data in sequence
            collections = [
                ("crypto", self._collect_crypto_data),
                ("account", self._collect_account_data),
                ("holdings", self._collect_holdings_data),
                ("historical_15min", self._collect_historical_data_15min),
                ("historical_60min", self._collect_historical_data_60min),
            ]

            for collection_name, collection_func in collections:
                try:
                    logger.info(f"Starting {collection_name} data collection")
                    success = collection_func()

                    if success:
                        logger.info(
                            f"{collection_name} data collection completed successfully"
                        )
                    else:
                        logger.error(f"{collection_name} data collection failed")
                        failed_collections.append(collection_name)

                except Exception as e:
                    logger.error(f"{collection_name} data collection crashed: {e}")
                    failed_collections.append(collection_name)

            # Determine overall success
            overall_success = len(failed_collections) == 0

            if overall_success:
                logger.info("All data collection completed successfully!")
            else:
                logger.warning(
                    f"Data collection completed with failures: {failed_collections}"
                )

            return overall_success, failed_collections

        except Exception as e:
            logger.error(f"Critical error during data collection: {e}")
            return False, ["critical_error"]

    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.db_manager:
                self.db_manager.close()
            logger.info("=== Robinhood Crypto Data Collector Finished ===")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point"""
    collector = None
    exit_code = 0

    try:
        # Initialize collector
        collector = RobinhoodDataCollector()

        # Run data collection
        success, failed = collector.run_data_collection()

        if not success:
            exit_code = 1
            if failed:
                logger.error(f"Failed collections: {', '.join(failed)}")

        collector.cleanup_old_historical_data()

    except Exception as e:
        logger.error(f"Application crashed: {e}", exc_info=True)
        exit_code = 2

    finally:
        # Cleanup
        if collector:
            collector.cleanup()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
