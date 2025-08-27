# utils/logger.py (Enhanced logging setup)
"""
Enhanced logging configuration with rotation and structured formatting
"""

import logging
import logging.handlers
import os
from typing import Dict, Any
from pathlib import Path

from config.settings import LoggingConfig


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """
    Setup enhanced logging with file rotation and structured formatting

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

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        config.file_path, maxBytes=config.max_file_size, backupCount=config.backup_count
    )
    file_handler.setLevel(getattr(logging, config.level.upper(), logging.DEBUG))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Return specific logger for the application
    app_logger = logging.getLogger("robinhood_crypto_app")
    return app_logger
