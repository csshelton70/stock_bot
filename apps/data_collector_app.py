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
import sys
from utils.logger import get_logger

logger = get_logger(__name__)


class DataCollectorApp(BaseApplication):
    """Data collection app with safe Unicode handling"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define platform-safe status indicators
        self.status_indicators = self._get_status_indicators()
        self.logger = get_logger(f"component.{self.__class__.__name__.lower()}")

    def _get_status_indicators(self) -> dict:
        """Get platform-appropriate status indicators"""
        if sys.platform.startswith("win"):
            # Windows-safe ASCII indicators
            return {
                "success": "[OK]",
                "failure": "[FAIL]",
                "warning": "[WARN]",
                "info": "[INFO]",
            }
        else:
            # Unix systems can handle Unicode
            return {"success": "✅", "failure": "❌", "warning": "⚠️", "info": "ℹ️"}

    def get_app_name(self) -> str:
        return "Robinhood Crypto Data Collector"

    def _setup_custom(self) -> None:
        """Setup all collectors using dynamic historical collector creation"""
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

        # Create collectors list
        collectors = []

        # Add Robinhood API-dependent collectors if available
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
            self.context.logger.info("Added Robinhood API collectors")
        else:
            self.context.logger.warning(
                "API client not available - skipping Robinhood collectors"
            )

        # Create historical collectors for each configured interval
        enabled_intervals = self.context.config.historical.get_enabled_intervals()

        for interval_config in enabled_intervals:
            collector = HistoricalCollector(
                db_manager=db_manager,
                retry_config=self.context.config.retry,
                historical_repo=historical_repo,
                crypto_repo=crypto_repo,
                days_back=interval_config.days_back,
                interval_minutes=interval_config.interval_minutes,
                buffer_days=interval_config.buffer_days,
            )
            collectors.append(collector)

            self.context.logger.info(
                f"Added historical collector: {interval_config.interval_minutes}min "
                f"({interval_config.days_back} days back)"
            )

        # Store collectors
        self.collectors = collectors
        self.context.logger.info(
            f"Setup complete with {len(collectors)} collectors "
            f"({len(enabled_intervals)} historical intervals)"
        )

    def _run_main(self) -> int:
        """Main data collection logic with safe Unicode logging"""
        success_count = 0
        failure_count = 0
        failed_collectors = []
        collector_results = {}

        for collector in self.collectors:
            collector_name = collector.get_collector_name()
            try:
                if collector.safe_collect_and_store():
                    success_count += 1
                    collector_results[collector_name] = "SUCCESS"
                else:
                    failure_count += 1
                    failed_collectors.append(collector_name)
                    collector_results[collector_name] = "FAILED"

            except Exception as e:
                self.context.error_handler.handle_error(
                    e,
                    f"{collector_name} collection",
                    extra_data={"collector": collector.__class__.__name__},
                )
                failure_count += 1
                failed_collectors.append(collector_name)
                collector_results[collector_name] = f"ERROR: {str(e)[:50]}..."

        # Enhanced summary logging with safe indicators
        self.context.logger.info("=" * 50)
        self.context.logger.info("Collection Summary")
        self.context.logger.info("=" * 50)
        self.context.logger.info(f"Total collectors: {len(self.collectors)}")
        self.context.logger.info(f"Successful: {success_count}")
        self.context.logger.info(f"Failed: {failure_count}")
        self.context.logger.info("-" * 50)

        # Log individual collector results with safe indicators
        for collector_name, result in collector_results.items():
            if result == "SUCCESS":
                status_indicator = self.status_indicators["success"]
            elif result == "FAILED":
                status_indicator = self.status_indicators["failure"]
            else:
                status_indicator = self.status_indicators["failure"]

            self.context.logger.info(f"  {status_indicator} {collector_name}: {result}")

        if failed_collectors:
            self.context.logger.warning(
                f"Failed collections: {', '.join(failed_collectors)}"
            )

        # Cleanup old data for each interval
        self._cleanup_old_data_for_all_intervals()

        # Return appropriate exit code with summary
        if failure_count == 0:
            self.context.logger.info(
                f"{self.status_indicators['success']} All collections completed successfully!"
            )
            return 0
        elif success_count > 0:
            self.context.logger.warning(
                f"{self.status_indicators['warning']} Partial success: {success_count}/{len(self.collectors)} completed"
            )
            return 1
        else:
            self.context.logger.error(
                f"{self.status_indicators['failure']} All collections failed!"
            )
            return 2

    def _cleanup_old_data_for_all_intervals(self) -> None:
        """Cleanup old historical data for all configured intervals"""
        try:
            db_manager = self.context.container.get("db_manager")
            from data.repositories.historical_repository import HistoricalRepository

            historical_repo = HistoricalRepository(db_manager)

            enabled_intervals = self.context.config.historical.get_enabled_intervals()
            total_deleted = 0

            for interval_config in enabled_intervals:
                if (
                    hasattr(interval_config, "cleanup_days")
                    and interval_config.cleanup_days > 0
                ):
                    try:
                        deleted_count = historical_repo.delete_old_data(
                            interval_config.cleanup_days
                        )
                        total_deleted += deleted_count

                        if deleted_count > 0:
                            self.context.logger.info(
                                f"Cleaned up {deleted_count} old records "
                                f"for {interval_config.interval_minutes}min interval"
                            )
                    except Exception as e:
                        self.context.error_handler.handle_error(
                            e,
                            f"cleanup for {interval_config.interval_minutes}min interval",
                        )

            if total_deleted > 0:
                self.context.logger.info(
                    f"Total cleanup: removed {total_deleted} old historical records"
                )

        except Exception as e:
            self.context.error_handler.handle_error(e, "historical data cleanup")
