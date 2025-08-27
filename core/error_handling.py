# core/error_handling.py
"""
Centralized error handling with structured logging
"""

import logging
import traceback
from typing import Optional, Dict, Any
from enum import Enum


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorHandler:
    """Centralized error handler with structured logging"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.error_count = 0
        self.error_history: list = []

    def handle_error(
        self,
        error: Exception,
        context: str = "",
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Handle an error with structured logging.

        Args:
            error: The exception that occurred
            context: Context information about where the error occurred
            severity: Error severity level
            extra_data: Additional data to include in logs
        """
        self.error_count += 1

        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "severity": severity.value,
            "stack_trace": traceback.format_exc(),
            "extra_data": extra_data or {},
        }

        self.error_history.append(error_info)

        # Log based on severity
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(
                f"CRITICAL ERROR in {context}: {error}", extra=error_info
            )
        elif severity == ErrorSeverity.HIGH:
            self.logger.error(f"ERROR in {context}: {error}", extra=error_info)
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"WARNING in {context}: {error}", extra=error_info)
        else:
            self.logger.info(f"INFO in {context}: {error}", extra=error_info)

    def handle_critical_error(self, error: Exception, context: str = "") -> None:
        """Handle critical errors that may require application shutdown"""
        self.handle_error(error, context, ErrorSeverity.CRITICAL)

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors encountered"""
        severity_counts = {}
        for error in self.error_history:
            severity = error["severity"]
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return {
            "total_errors": self.error_count,
            "severity_breakdown": severity_counts,
            "recent_errors": self.error_history[-5:] if self.error_history else [],
        }
