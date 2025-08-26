# ./utils/logger.py
"""
Logging setup for Robinhood Crypto Trading App
"""

# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring,missing-function-docstring

import logging
import os
from logging.handlers import RotatingFileHandler
from utils.config import Config


def setup_logging(config: Config) -> logging.Logger:
    """Setup logging with both console and file handlers"""

    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(config.log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create logger
    logger = logging.getLogger("robinhood_crypto_app")
    logger.setLevel(logging.DEBUG)  # Capture everything, handlers will filter

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    simple_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # File handler - logs everything (DEBUG and above)
    file_handler = RotatingFileHandler(
        config.log_file_path,
        maxBytes=config.max_file_size_mb * 1024 * 1024,  # Convert MB to bytes
        backupCount=config.backup_count,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    # Console handler - logs less detail (INFO and above by default)
    console_handler = logging.StreamHandler()
    console_level = getattr(logging, config.log_level.upper(), logging.INFO)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    return logger
