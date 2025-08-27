# collectors/base_collector.py
"""
Base collector class with standardized error handling and database operations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

from database.connections import DatabaseManager
from utils.retry import RetryConfig, retry_with_backoff


class BaseCollector(ABC):
    """Base class for data collectors with common functionality"""

    def __init__(self, db_manager: DatabaseManager, retry_config: RetryConfig):
        self.db_manager = db_manager
        self.retry_config = retry_config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_collector_name(self) -> str:
        """Return collector name for logging"""
        pass

    @abstractmethod
    def collect_and_store(self) -> bool:
        """
        Collect data and store in database.

        Returns:
            True if successful, False otherwise
        """
        pass

    @retry_with_backoff()
    def safe_collect_and_store(self) -> bool:
        """Wrapper method with retry logic"""
        try:
            self.logger.info(f"--- {self.get_collector_name()} Collection Starting ---")
            success = self.collect_and_store()

            if success:
                self.logger.info(
                    f"--- {self.get_collector_name()} Collection Completed Successfully ---"
                )
            else:
                self.logger.error(
                    f"--- {self.get_collector_name()} Collection Failed ---"
                )

            return success

        except Exception as e:
            self.logger.error(f"{self.get_collector_name()} collection error: {e}")
            raise

    def validate_data(self, data: Any) -> bool:
        """Validate collected data before storage"""
        return data is not None

    def log_collection_stats(self, stats: Dict[str, Any]) -> None:
        """Log collection statistics"""
        self.logger.info(f"{self.get_collector_name()} Statistics:")
        for key, value in stats.items():
            self.logger.info(f"  {key}: {value}")
