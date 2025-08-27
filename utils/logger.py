# utils/logger.py - Fixed logging setup with proper Unicode handling
"""
Enhanced logging configuration with Unicode support for Windows
"""

import logging
import logging.handlers
import os
import sys
from typing import Dict, Any
from pathlib import Path

from config.settings import LoggingConfig


class UnicodeConsoleHandler(logging.StreamHandler):
    """Console handler that safely handles Unicode characters on Windows"""

    def emit(self, record):
        try:
            msg = self.format(record)
            # Replace problematic Unicode characters with ASCII equivalents
            msg = self._sanitize_unicode(msg)

            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

    def _sanitize_unicode(self, text: str) -> str:
        """Replace Unicode characters with ASCII equivalents"""
        # Map problematic Unicode characters to ASCII equivalents
        unicode_map = {
            "✅": "[OK]",  # Check mark
            "❌": "[FAIL]",  # Cross mark
            "⚠️": "[WARN]",  # Warning sign
            "📊": "[DATA]",  # Chart
            "🔄": "[SYNC]",  # Arrows
            "💰": "[MONEY]",  # Money bag
            "📈": "[UP]",  # Trending up
            "📉": "[DOWN]",  # Trending down
        }

        for unicode_char, ascii_replacement in unicode_map.items():
            text = text.replace(unicode_char, ascii_replacement)

        return text


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """
    Setup enhanced logging with Unicode support for Windows

    Args:
        config: Logging configuration

    Returns:
        Configured logger instance
    """

    # Create logs directory if it doesn't exist
    log_file_path = Path(config.file_path)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(config.format)

    # Console handler with Unicode support
    if sys.platform.startswith("win"):
        # Use custom Unicode handler for Windows
        console_handler = UnicodeConsoleHandler()
    else:
        # Use standard handler for Unix-like systems
        console_handler = logging.StreamHandler()

    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with UTF-8 encoding
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_file_size,
            backupCount=config.backup_count,
            encoding="utf-8",  # Explicitly use UTF-8 for file logging
        )
        file_handler.setLevel(getattr(logging, config.level.upper(), logging.DEBUG))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # Fallback to console logging if file handler fails
        console_handler.setLevel(logging.DEBUG)
        root_logger.error(f"Failed to setup file logging: {e}")

    # Return specific logger for the application
    app_logger = logging.getLogger("robinhood_crypto_app")
    return app_logger
