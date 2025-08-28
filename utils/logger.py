# utils/logger.py - Enhanced standardized logging system
"""
Enhanced logging configuration with Unicode support for Windows
Provides standardized logger registration for all project files
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from config.settings import LoggingConfig

# Global logger registry to track registered loggers
_LOGGER_REGISTRY: Dict[str, logging.Logger] = {}
_ROOT_LOGGER_SETUP = False
_APP_NAME = "robinhood_crypto_app"


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds color codes to log levels"""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"  # Reset to default color

    def format(self, record):
        # Get the original formatted message
        formatted = super().format(record)

        # Only add colors if we're outputting to a terminal
        if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
            level_name = record.levelname
            if level_name in self.COLORS:
                formatted = f"{self.COLORS[level_name]}{formatted}{self.RESET}"

        return formatted


class UnicodeConsoleHandler(logging.StreamHandler):
    """Console handler that safely handles Unicode characters on Windows"""

    def emit(self, record):
        try:
            msg = self.format(record)
            msg = self._sanitize_unicode(msg)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

    def _sanitize_unicode(self, text: str) -> str:
        """Replace Unicode characters with ASCII equivalents"""
        unicode_map = {
            "✅": "✓",  # Check mark
            "❌": "✗",  # Cross mark
            "⚠️": "!",  # Warning sign
            "📊": "[DATA]",  # Chart
            "🔄": "↻",  # Arrows
            "💰": "$",  # Money bag
            "📈": "↗",  # Trending up
            "📉": "↘",  # Trending down
        }

        for unicode_char, ascii_replacement in unicode_map.items():
            text = text.replace(unicode_char, ascii_replacement)

        return text


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """
    Setup enhanced logging with Unicode support and standardized configuration

    Args:
        config: Logging configuration

    Returns:
        Main application logger instance
    """
    global _ROOT_LOGGER_SETUP

    if _ROOT_LOGGER_SETUP:
        return get_logger(_APP_NAME)

    # Create logs directory if it doesn't exist
    log_file_path = Path(config.file_path)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create formatters
    colored_formatter = ColoredFormatter(config.format)
    file_formatter = logging.Formatter(config.format)

    # Console handler with Unicode support and color
    if sys.platform.startswith("win"):
        console_handler = UnicodeConsoleHandler()
    else:
        console_handler = logging.StreamHandler()

    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(colored_formatter)
    root_logger.addHandler(console_handler)

    # File handler with UTF-8 encoding
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_file_size,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, config.level.upper(), logging.DEBUG))
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        console_handler.setLevel(logging.DEBUG)
        root_logger.error(f"Failed to setup file logging: {e}")

    _ROOT_LOGGER_SETUP = True

    # Return the main application logger
    return get_logger(_APP_NAME)


def get_logger(name: str, module_path: Optional[str] = None) -> logging.Logger:
    """
    Get a standardized logger for a module

    Args:
        name: Logger name (typically __name__ or module identifier)
        module_path: Optional module path for better identification

    Returns:
        Configured logger instance

    Example:
        # In any module file:
        from utils.logger import get_logger
        logger = get_logger(__name__)

        # Or with custom name:
        logger = get_logger("database.connections")
    """
    # Normalize the logger name to follow consistent hierarchy
    if name == "__main__":
        logger_name = _APP_NAME
    elif name.startswith(_APP_NAME):
        logger_name = name
    else:
        # Convert module paths to consistent naming
        if name.startswith("__"):
            logger_name = f"{_APP_NAME}.main"
        else:
            # Remove any leading dots and normalize
            clean_name = name.lstrip(".")
            logger_name = f"{_APP_NAME}.{clean_name}"

    # Check if logger already exists in registry
    if logger_name in _LOGGER_REGISTRY:
        return _LOGGER_REGISTRY[logger_name]

    # Create new logger
    logger = logging.getLogger(logger_name)

    # Store in registry
    _LOGGER_REGISTRY[logger_name] = logger

    # Add module path info if provided
    if module_path:
        logger.addFilter(
            lambda record: setattr(record, "module_path", module_path) or True
        )

    return logger


def get_child_logger(parent_name: str, child_name: str) -> logging.Logger:
    """
    Get a child logger for sub-components

    Args:
        parent_name: Parent logger name
        child_name: Child component name

    Returns:
        Child logger instance

    Example:
        # In a module with sub-components:
        main_logger = get_logger(__name__)
        api_logger = get_child_logger(__name__, "api_client")
    """
    parent_logger_name = (
        f"{_APP_NAME}.{parent_name}"
        if not parent_name.startswith(_APP_NAME)
        else parent_name
    )
    child_logger_name = f"{parent_logger_name}.{child_name}"

    return get_logger(child_logger_name)


def list_registered_loggers() -> Dict[str, str]:
    """
    List all registered loggers for debugging

    Returns:
        Dictionary of logger names and their effective levels
    """
    return {
        name: logging.getLevelName(logger.getEffectiveLevel())
        for name, logger in _LOGGER_REGISTRY.items()
    }


def configure_module_logger(
    module_name: str,
    level: Optional[str] = None,
    additional_handlers: Optional[list] = None,
) -> logging.Logger:
    """
    Configure a logger for a specific module with custom settings

    Args:
        module_name: Module name (typically __name__)
        level: Optional log level override
        additional_handlers: Optional additional handlers

    Returns:
        Configured logger

    Example:
        # For modules that need special handling:
        logger = configure_module_logger(__name__, level="DEBUG")
    """
    logger = get_logger(module_name)

    if level:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if additional_handlers:
        for handler in additional_handlers:
            logger.addHandler(handler)

    return logger


def setup_test_logging() -> logging.Logger:
    """
    Setup minimal logging for tests

    Returns:
        Test logger instance
    """
    # Create a simple formatter for tests
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler only for tests
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)

    # Setup root logger for tests
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    return get_logger("test")


# Convenience function for backward compatibility
def setup_module_logger(module_name: str) -> logging.Logger:
    """
    DEPRECATED: Use get_logger() instead
    Setup logger for a module (backward compatibility)
    """
    import warnings

    warnings.warn(
        "setup_module_logger is deprecated, use get_logger() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_logger(module_name)
