# Updated apps/data_collector_app.py to use the new historical collector
"""
Updated Data Collection Application using the refactored historical collector
"""
from typing import List
from core.application import BaseApplication
from collectors.crypto_collector import CryptoCollector
from collectors.account_collector import AccountCollector
from collectors.holdings_collector import HoldingsCollector
from collectors.historical_collector import HistoricalCollector


class DataCollectorApp(BaseApplication):
    """Complete data collection app with all refactored collectors"""

    def get_app_name(self) -> str:
        return "Robinhood Crypto Data Collector (Complete)"

    def _setup_custom(self) -> None:
        """Setup all collectors using the refactored architecture"""
        # Get dependencies from container
        db_manager = self.context.container.get("db_manager")
        crypto_repo = self.context.container.get("crypto_repo")

        # Create historical repository
        from data.repositories.historical_repository import HistoricalRepository

        historical_repo = HistoricalRepository(db_manager)

        # Get API client if available
        api_client = None
        if self.context.container.has("api_client"):
            api_client = self.context.container.get("api_client")

        # Create collectors
        collectors = []

        if api_client:
            collectors.extend(
                [
                    CryptoCollector(
                        db_manager, self.context.config.retry, crypto_repo, api_client
                    ),
                    AccountCollector(db_manager, self.context.config.retry, api_client),
                    HoldingsCollector(
                        db_manager, self.context.config.retry, api_client, crypto_repo
                    ),
                ]
            )
        else:
            self.context.logger.warning(
                "API client not available - skipping Robinhood collectors"
            )

        # Add refactored historical collector
        collectors.append(
            HistoricalCollector(
                db_manager=db_manager,
                retry_config=self.context.config.retry,
                historical_repo=historical_repo,
                crypto_repo=crypto_repo,
                days_back=self.context.config.historical.days_back,
                interval_minutes=self.context.config.historical.interval_minutes,
                buffer_days=self.context.config.historical.buffer_days,
            )
        )

        collectors.append(
            HistoricalCollector(
                db_manager=db_manager,
                retry_config=self.context.config.retry,
                historical_repo=historical_repo,
                crypto_repo=crypto_repo,
                days_back=self.context.config.historical.days_back,
                interval_minutes=60,
                buffer_days=self.context.config.historical.buffer_days,
            )
        )

        # Store collectors
        self.collectors = collectors
        self.context.logger.info(f"Setup complete with {len(collectors)} collectors")

    def _run_main(self) -> int:
        """Main data collection logic"""
        success_count = 0
        failure_count = 0
        failed_collectors = []

        for collector in self.collectors:
            try:
                if collector.safe_collect_and_store():
                    success_count += 1
                else:
                    failure_count += 1
                    failed_collectors.append(collector.get_collector_name())

            except Exception as e:
                self.context.error_handler.handle_error(
                    e,
                    f"{collector.get_collector_name()} collection",
                    extra_data={"collector": collector.__class__.__name__},
                )
                failure_count += 1
                failed_collectors.append(collector.get_collector_name())

        # Log summary
        self.context.logger.info(f"=== Collection Summary ===")
        self.context.logger.info(f"Successful: {success_count}")
        self.context.logger.info(f"Failed: {failure_count}")

        if failed_collectors:
            self.context.logger.warning(
                f"Failed collections: {', '.join(failed_collectors)}"
            )

        # Cleanup old data if configured
        self._cleanup_old_data()

        return 0 if failure_count == 0 else (1 if success_count > 0 else 2)

    def _cleanup_old_data(self) -> None:
        """Cleanup old historical data using repository"""
        try:
            if hasattr(self.context.config.historical, "cleanup_days"):
                # Get historical repository
                db_manager = self.context.container.get("db_manager")
                from data.repositories.historical_repository import HistoricalRepository

                historical_repo = HistoricalRepository(db_manager)

                cleanup_days = self.context.config.historical.cleanup_days
                deleted_count = historical_repo.delete_old_data(cleanup_days)

                if deleted_count > 0:
                    self.context.logger.info(
                        f"Cleaned up {deleted_count} old historical records"
                    )

        except Exception as e:
            self.context.error_handler.handle_error(e, "historical data cleanup")
