# utils/logger.py - Fixed logging setup with proper Unicode handling
"""
Enhanced logging configuration with Unicode support for Windows
"""

# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation, import-outside-toplevel

# Standard Import
import logging
import logging.handlers
import sys
from pathlib import Path

# Third Party Imports

# First Party Imports
from config.settings import LoggingConfig

# Local Imports




class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds color codes to log levels"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'  # Reset to default color
    
    def format(self, record):
        # Get the original formatted message
        formatted = super().format(record)
        
        # Only add colors if we're outputting to a terminal (not when redirected to file)
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            level_name = record.levelname
            if level_name in self.COLORS:
                # Color the entire message
                formatted = f"{self.COLORS[level_name]}{formatted}{self.RESET}"
        
        return formatted


class UnicodeConsoleHandler(logging.StreamHandler):
    """Console handler that safely handles Unicode characters on Windows with color support"""

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
        # Map problematic Unicode characters to ASCII equivalents with color-friendly alternatives
        unicode_map = {
            "✅": "✓",      # Check mark (simpler Unicode)
            "❌": "✗",      # Cross mark (simpler Unicode)
            "⚠️": "!",      # Warning sign
            "📊": "[DATA]", # Chart
            "🔄": "↻",      # Arrows (simpler Unicode)
            "💰": "$",      # Money bag
            "📈": "↗",      # Trending up
            "📉": "↘",      # Trending down
        }

        for unicode_char, ascii_replacement in unicode_map.items():
            text = text.replace(unicode_char, ascii_replacement)

        return text


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """
    Setup enhanced logging with Unicode support for Windows and color coding

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

    # Create colored formatter for console
    colored_formatter = ColoredFormatter(config.format)
    
    # Create regular formatter for file (no colors in files)
    file_formatter = logging.Formatter(config.format)

    # Console handler with Unicode support and color
    if sys.platform.startswith("win"):
        # Use custom Unicode handler for Windows
        console_handler = UnicodeConsoleHandler()
    else:
        # Use standard handler for Unix-like systems
        console_handler = logging.StreamHandler()

    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(colored_formatter)  # Use colored formatter for console
    root_logger.addHandler(console_handler)

    # File handler with UTF-8 encoding (no colors)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_file_size,
            backupCount=config.backup_count,
            encoding="utf-8",  # Explicitly use UTF-8 for file logging
        )
        file_handler.setLevel(getattr(logging, config.level.upper(), logging.DEBUG))
        file_handler.setFormatter(file_formatter)  # Use regular formatter for file
        root_logger.addHandler(file_handler)
    except Exception as e:
        # Fallback to console logging if file handler fails
        console_handler.setLevel(logging.DEBUG)
        root_logger.error(f"Failed to setup file logging: {e}")

    # Return specific logger for the application
    app_logger = logging.getLogger("robinhood_crypto_app")
    return app_logger
