# collectors/base_collector.py
"""
Base collector class with standardized error handling and database operations
ENHANCED: Improved validation, error handling, and duplicate prevention support
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

from data import DatabaseManager
from utils import RetryConfig, retry_with_backoff

from utils.logger import get_logger

logger = get_logger(__name__)


class BaseCollector(ABC):
    """
    Base class for data collectors with common functionality
    ENHANCED: Better validation, error handling, and statistics tracking
    """

    def __init__(self, db_manager: DatabaseManager, retry_config: RetryConfig):
        self.db_manager = db_manager
        self.retry_config = retry_config
        self.logger = get_logger(f"collectors.{self.__class__.__name__.lower()}")
        self.collection_start_time = None
        self.collection_stats = {}

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
        """
        Wrapper method with retry logic and enhanced error handling
        ENHANCED: Comprehensive logging and statistics tracking
        """
        try:
            self.collection_start_time = datetime.utcnow()
            collector_name = self.get_collector_name()

            self.logger.info(f"--- {collector_name} Collection Starting ---")
            self.logger.info(f"Start time: {self.collection_start_time}")

            success = self.collect_and_store()

            # Calculate collection duration
            end_time = datetime.utcnow()
            duration = (end_time - self.collection_start_time).total_seconds()

            if success:
                self.logger.info(
                    f"--- {collector_name} Collection Completed Successfully ---"
                )
                self.logger.info(f"Duration: {duration:.2f} seconds")
            else:
                self.logger.error(f"--- {collector_name} Collection Failed ---")
                self.logger.error(f"Duration: {duration:.2f} seconds")

            # Log final statistics if available
            if hasattr(self, "collection_stats") and self.collection_stats:
                self._log_final_statistics()

            return success

        except Exception as e:
            collector_name = self.get_collector_name()
            duration = 0
            if self.collection_start_time:
                duration = (
                    datetime.utcnow() - self.collection_start_time
                ).total_seconds()

            self.logger.error(
                f"{collector_name} collection error after {duration:.2f}s: {e}"
            )
            raise

    def validate_data(self, data: Any) -> bool:
        """
        Validate collected data before storage
        ENHANCED: More comprehensive validation with detailed logging
        """
        if data is None:
            self.logger.warning("Data validation failed: data is None")
            return False

        # Enhanced validation for different data types
        if isinstance(data, list):
            if len(data) == 0:
                self.logger.info(
                    "Data validation: empty list (valid but no data to process)"
                )
                return True

            # Validate list elements
            return self._validate_list_data(data)

        elif isinstance(data, dict):
            # For dictionary data (like account info)
            return self._validate_dict_data(data)

        else:
            # For other data types
            self.logger.debug(f"Data validation: {type(data).__name__} data accepted")
            return True

    def _validate_list_data(self, data: List[Any]) -> bool:
        """Validate list-based data (like historical records, holdings)"""
        try:
            total_records = len(data)
            valid_records = 0

            for i, record in enumerate(data[:10]):  # Check first 10 records as sample
                if isinstance(record, dict):
                    if self._validate_record_structure(record):
                        valid_records += 1
                    else:
                        self.logger.debug(
                            f"Invalid record structure at index {i}: {record}"
                        )
                else:
                    self.logger.warning(f"Non-dict record at index {i}: {type(record)}")

            # Consider valid if at least 80% of sample records are valid
            sample_size = min(10, total_records)
            validity_ratio = valid_records / sample_size if sample_size > 0 else 0

            is_valid = validity_ratio >= 0.8

            self.logger.debug(
                f"List validation: {valid_records}/{sample_size} sample records valid "
                f"({validity_ratio:.1%}), Total records: {total_records}"
            )

            if not is_valid:
                self.logger.warning(
                    f"Data validation failed: only {validity_ratio:.1%} of records are valid"
                )

            return is_valid

        except Exception as e:
            self.logger.error(f"Error validating list data: {e}")
            return False

    def _validate_dict_data(self, data: Dict[str, Any]) -> bool:
        """Validate dictionary-based data (like account info)"""
        try:
            # Check if dictionary has some content
            if not data:
                self.logger.warning("Data validation failed: empty dictionary")
                return False

            # Basic structure validation
            return len(data) > 0

        except Exception as e:
            self.logger.error(f"Error validating dict data: {e}")
            return False

    def _validate_record_structure(self, record: Dict[str, Any]) -> bool:
        """Validate individual record structure - override in subclasses for specific validation"""
        try:
            # Basic validation - check for non-empty dictionary
            return isinstance(record, dict) and len(record) > 0
        except Exception:
            return False

    def log_collection_stats(self, stats: Dict[str, Any]) -> None:
        """
        Log collection statistics with enhanced formatting
        ENHANCED: Better formatting and statistics preservation
        """
        self.collection_stats = stats  # Store for later use

        collector_name = self.get_collector_name()
        self.logger.info(f"📊 {collector_name} Statistics:")

        # Format different types of statistics
        for key, value in stats.items():
            if isinstance(value, (int, float)):
                if key.lower().find("count") >= 0 or key.lower().find("records") >= 0:
                    self.logger.info(f"   {key}: {value:,}")
                elif key.lower().find("percent") >= 0 or key.lower().find("rate") >= 0:
                    self.logger.info(f"   {key}: {value:.2f}%")
                else:
                    self.logger.info(f"   {key}: {value}")
            else:
                self.logger.info(f"   {key}: {value}")

    def _log_final_statistics(self) -> None:
        """Log final collection statistics with duration"""
        if not self.collection_stats or not self.collection_start_time:
            return

        try:
            duration = (datetime.utcnow() - self.collection_start_time).total_seconds()

            # Calculate rates if applicable
            enhanced_stats = dict(self.collection_stats)
            enhanced_stats["collection_duration_seconds"] = f"{duration:.2f}"

            # Calculate records per second if we have record counts
            for key, value in self.collection_stats.items():
                if isinstance(value, int) and (
                    "records" in key.lower()
                    or "inserted" in key.lower()
                    or "processed" in key.lower()
                ):
                    if value > 0 and duration > 0:
                        rate = value / duration
                        enhanced_stats[f"{key}_per_second"] = f"{rate:.2f}"

            self.logger.info("📈 Final Collection Summary:")
            for key, value in enhanced_stats.items():
                self.logger.info(f"   {key}: {value}")

        except Exception as e:
            self.logger.debug(f"Error logging final statistics: {e}")

    def get_collection_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the last collection
        NEW METHOD: Provides health metrics for monitoring
        """
        try:
            if not self.collection_stats:
                return {
                    "status": "no_data",
                    "message": "No collection statistics available",
                }

            # Determine health based on error rates
            total_processed = 0
            total_errors = 0

            for key, value in self.collection_stats.items():
                if isinstance(value, int):
                    if "processed" in key.lower() or "total" in key.lower():
                        total_processed += value
                    elif "error" in key.lower() or "failed" in key.lower():
                        total_errors += value

            if total_processed == 0:
                return {"status": "no_activity", "message": "No records processed"}

            error_rate = (
                (total_errors / total_processed) * 100 if total_processed > 0 else 0
            )

            if error_rate == 0:
                status = "healthy"
                message = "All operations completed successfully"
            elif error_rate < 5:
                status = "warning"
                message = f"Low error rate: {error_rate:.1f}%"
            elif error_rate < 20:
                status = "degraded"
                message = f"Moderate error rate: {error_rate:.1f}%"
            else:
                status = "unhealthy"
                message = f"High error rate: {error_rate:.1f}%"

            return {
                "status": status,
                "message": message,
                "error_rate_percent": round(error_rate, 2),
                "total_processed": total_processed,
                "total_errors": total_errors,
                "collection_stats": self.collection_stats,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error calculating health status: {e}",
                "collection_stats": self.collection_stats,
            }

    def pre_collection_check(self) -> bool:
        """
        Perform pre-collection validation checks
        NEW METHOD: Validates system state before collection
        """
        try:
            # Check database connectivity
            if not self._check_database_connectivity():
                self.logger.error(
                    "Pre-collection check failed: database not accessible"
                )
                return False

            # Check available disk space (basic check)
            if not self._check_disk_space():
                self.logger.warning("Pre-collection check warning: low disk space")

            self.logger.debug("Pre-collection checks passed")
            return True

        except Exception as e:
            self.logger.error(f"Pre-collection check error: {e}")
            return False

    def _check_database_connectivity(self) -> bool:
        """Check if database is accessible"""
        try:
            with self.db_manager.get_session() as session:
                # Simple query to test connectivity
                session.execute("SELECT 1").fetchone()
            return True
        except Exception as e:
            self.logger.error(f"Database connectivity check failed: {e}")
            return False

    def _check_disk_space(self) -> bool:
        """Basic disk space check"""
        try:
            import shutil

            db_path = self.db_manager.database_path

            # Get free space in GB
            free_space_gb = shutil.disk_usage(os.path.dirname(db_path)).free / (1024**3)

            if free_space_gb < 1.0:  # Less than 1GB free
                self.logger.warning(f"Low disk space: {free_space_gb:.2f} GB free")
                return False

            self.logger.debug(f"Disk space OK: {free_space_gb:.2f} GB free")
            return True

        except Exception as e:
            self.logger.debug(f"Could not check disk space: {e}")
            return True  # Don't fail collection for this

    def post_collection_summary(self) -> Dict[str, Any]:
        """
        Generate post-collection summary report
        NEW METHOD: Comprehensive summary of collection results
        """
        try:
            summary = {
                "collector_name": self.get_collector_name(),
                "collection_timestamp": self.collection_start_time,
                "duration_seconds": 0,
                "status": "unknown",
                "statistics": self.collection_stats,
                "health": self.get_collection_health_status(),
            }

            if self.collection_start_time:
                duration = (
                    datetime.utcnow() - self.collection_start_time
                ).total_seconds()
                summary["duration_seconds"] = round(duration, 2)

            # Determine overall status
            health_status = summary["health"]["status"]
            if health_status == "healthy":
                summary["status"] = "success"
            elif health_status in ["warning", "degraded"]:
                summary["status"] = "partial_success"
            else:
                summary["status"] = "failed"

            return summary

        except Exception as e:
            self.logger.error(f"Error generating post-collection summary: {e}")
            return {
                "collector_name": self.get_collector_name(),
                "status": "error",
                "error": str(e),
            }

    def log_collection_progress(
        self, message: str, progress_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log collection progress with optional data
        NEW METHOD: Provides progress updates during long-running collections
        """
        try:
            duration = 0
            if self.collection_start_time:
                duration = (
                    datetime.utcnow() - self.collection_start_time
                ).total_seconds()

            progress_msg = f"[{duration:6.1f}s] {message}"

            if progress_data:
                # Format progress data
                data_str = ", ".join(f"{k}={v}" for k, v in progress_data.items())
                progress_msg += f" ({data_str})"

            self.logger.info(progress_msg)

        except Exception as e:
            self.logger.debug(f"Error logging progress: {e}")

    def handle_collection_error(self, error: Exception, context: str = "") -> None:
        """
        Handle collection errors with structured logging
        NEW METHOD: Standardized error handling across collectors
        """
        try:
            error_context = f"{self.get_collector_name()}"
            if context:
                error_context += f" - {context}"

            duration = 0
            if self.collection_start_time:
                duration = (
                    datetime.utcnow() - self.collection_start_time
                ).total_seconds()

            self.logger.error(
                f"Collection error in {error_context} after {duration:.1f}s: {error}",
                extra={
                    "collector": self.__class__.__name__,
                    "error_type": type(error).__name__,
                    "context": context,
                    "duration_seconds": duration,
                },
            )

        except Exception as log_error:
            # Fallback logging if structured logging fails
            self.logger.error(f"Collection error: {error} (logging error: {log_error})")

    def validate_historical_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate historical record structure - can be overridden by subclasses
        NEW METHOD: Specific validation for historical data records
        """
        try:
            required_fields = [
                "symbol",
                "timestamp",
                "interval_minutes",
                "open",
                "high",
                "low",
                "close",
            ]

            # Check required fields
            for field in required_fields:
                if field not in record:
                    self.logger.debug(f"Missing required field: {field}")
                    return False

            # Validate data types and ranges
            try:
                open_price = float(record["open"])
                high = float(record["high"])
                low = float(record["low"])
                close = float(record["close"])

                # OHLC validation
                if not (low <= open_price <= high and low <= close <= high):
                    self.logger.debug(f"Invalid OHLC relationship in record")
                    return False

                # Positive price validation
                if any(val <= 0 for val in [open_price, high, low, close]):
                    self.logger.debug(f"Non-positive price values in record")
                    return False

            except (ValueError, TypeError) as e:
                self.logger.debug(f"Invalid numeric values in record: {e}")
                return False

            # Validate timestamp
            if not isinstance(record["timestamp"], datetime):
                self.logger.debug(
                    f"Invalid timestamp type: {type(record['timestamp'])}"
                )
                return False

            # Validate interval
            interval = record["interval_minutes"]
            if not isinstance(interval, int) or interval <= 0:
                self.logger.debug(f"Invalid interval_minutes: {interval}")
                return False

            return True

        except Exception as e:
            self.logger.debug(f"Error validating historical record: {e}")
            return False

    def validate_crypto_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate crypto record structure
        NEW METHOD: Specific validation for crypto market data
        """
        try:
            # Required field
            if "symbol" not in record or not record["symbol"]:
                return False

            # Optional numeric fields that should be positive if present
            numeric_fields = ["minimum_order", "maximum_order", "bid", "ask", "mid"]
            for field in numeric_fields:
                if field in record and record[field] is not None:
                    try:
                        value = float(record[field])
                        if value < 0:
                            self.logger.debug(f"Negative value for {field}: {value}")
                            return False
                    except (ValueError, TypeError):
                        self.logger.debug(
                            f"Invalid numeric value for {field}: {record[field]}"
                        )
                        return False

            return True

        except Exception as e:
            self.logger.debug(f"Error validating crypto record: {e}")
            return False

    def validate_holdings_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate holdings record structure
        NEW METHOD: Specific validation for holdings data
        """
        try:
            # Required fields
            required_fields = ["asset_code", "total_quantity"]
            for field in required_fields:
                if field not in record:
                    return False

            # Validate quantities
            try:
                total_qty = float(record["total_quantity"])
                if total_qty < 0:
                    return False

                # Validate available quantity if present
                if "quantity_available_for_trading" in record:
                    available_qty = float(record["quantity_available_for_trading"])
                    if available_qty < 0 or available_qty > total_qty:
                        return False

            except (ValueError, TypeError):
                return False

            return True

        except Exception as e:
            self.logger.debug(f"Error validating holdings record: {e}")
            return False

    def _validate_record_structure(self, record: Dict[str, Any]) -> bool:
        """
        Validate record structure - routes to appropriate validator
        ENHANCED: Intelligent validation routing based on collector type
        """
        collector_class = self.__class__.__name__.lower()

        if "historical" in collector_class:
            return self.validate_historical_record(record)
        elif "crypto" in collector_class:
            return self.validate_crypto_record(record)
        elif "holdings" in collector_class:
            return self.validate_holdings_record(record)
        else:
            # Generic validation for other collectors
            return isinstance(record, dict) and len(record) > 0

    def create_collection_report(self) -> Dict[str, Any]:
        """
        Create comprehensive collection report for monitoring
        NEW METHOD: Detailed report for system monitoring and debugging
        """
        try:
            report = {
                "collector_info": {
                    "name": self.get_collector_name(),
                    "class": self.__class__.__name__,
                    "start_time": self.collection_start_time,
                    "end_time": datetime.utcnow(),
                },
                "performance": {"duration_seconds": 0, "success": False},
                "statistics": self.collection_stats,
                "health_status": self.get_collection_health_status(),
                "recommendations": [],
            }

            # Calculate performance metrics
            if self.collection_start_time:
                duration = (
                    datetime.utcnow() - self.collection_start_time
                ).total_seconds()
                report["performance"]["duration_seconds"] = round(duration, 2)

            # Add recommendations based on performance
            health_status = report["health_status"]["status"]
            if health_status == "unhealthy":
                report["recommendations"].append(
                    "Review error logs and check API connectivity"
                )
            elif health_status == "degraded":
                report["recommendations"].append(
                    "Monitor error patterns and consider retry adjustments"
                )
            elif duration > 300:  # More than 5 minutes
                report["recommendations"].append(
                    "Consider optimizing collection strategy for better performance"
                )

            # Success determination
            report["performance"]["success"] = health_status in ["healthy", "warning"]

            return report

        except Exception as e:
            return {
                "collector_info": {
                    "name": self.get_collector_name(),
                    "class": self.__class__.__name__,
                },
                "error": f"Error creating collection report: {e}",
                "performance": {"success": False},
            }
