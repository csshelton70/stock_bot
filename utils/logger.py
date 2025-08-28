# utils/logger.py - Enhanced logging system with detailed error location tracking
"""
Enhanced logging configuration with Unicode support, detailed error location tracking,
and standardized logger registration for all project files
"""

import logging
import logging.handlers
import sys
import traceback
import inspect
from pathlib import Path
from typing import Optional, Dict, Any, Union

from config.settings import LoggingConfig

# Global logger registry to track registered loggers
_LOGGER_REGISTRY: Dict[str, logging.Logger] = {}
_ROOT_LOGGER_SETUP = False
_APP_NAME = "crypto_app"


class DetailedFormatter(logging.Formatter):
    """Enhanced formatter with conditional file location information"""
    
    def __init__(self, include_colors=True):
        self.include_colors = include_colors
        # Base format without location details
        self.base_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        # Enhanced format with location details for warnings and higher
        self.detailed_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[%(clean_filename)s:%(funcName)s:%(lineno)d] - %(message)s"
        )
        super().__init__(self.base_format)
    
    def format(self, record):
        # Determine if we should include location info (WARNING and higher)
        include_location = record.levelno >= logging.WARNING
        
        # Clean up filename to remove __init__.py references
        if hasattr(record, 'filename'):
            if record.filename == '__init__.py':
                # Use the directory name instead of __init__.py
                path_parts = Path(record.pathname).parts
                if len(path_parts) >= 2:
                    record.clean_filename = path_parts[-2]  # Use parent directory name
                else:
                    record.clean_filename = 'main'
            else:
                record.clean_filename = record.filename
        else:
            record.clean_filename = 'unknown'
        
        # Use appropriate format based on log level
        if include_location:
            self._style._fmt = self.detailed_format
        else:
            self._style._fmt = self.base_format
        
        # Format the base message
        formatted = super().format(record)
        
        # Add colors if enabled and outputting to terminal
        if (self.include_colors and 
            hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()):
            formatted = self._add_colors(formatted, record.levelname)
        
        return formatted
    
    def _add_colors(self, message: str, level: str) -> str:
        """Add ANSI color codes based on log level"""
        colors = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
        }
        reset = '\033[0m'
        
        if level in colors:
            return f"{colors[level]}{message}{reset}"
        return message


class EnhancedUnicodeHandler(logging.StreamHandler):
    """Enhanced console handler with Unicode support and error location tracking"""

    def emit(self, record):
        try:
            # Enhance record with additional context if this is an exception
            if record.exc_info:
                record.stack_trace = ''.join(traceback.format_exception(*record.exc_info))
                
                # Extract specific error location from traceback
                tb = record.exc_info[2]
                if tb:
                    # Get the last frame in the traceback (where error occurred)
                    while tb.tb_next:
                        tb = tb.tb_next
                    
                    error_frame = tb.tb_frame
                    error_file = Path(error_frame.f_code.co_filename)
                    
                    # Try to get relative path
                    try:
                        relative_path = error_file.relative_to(Path.cwd())
                        record.error_file = str(relative_path)
                    except ValueError:
                        record.error_file = error_file.name
                    
                    record.error_function = error_frame.f_code.co_name
                    record.error_line = tb.tb_lineno
            
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
            "✅": "✓",      # Check mark
            "❌": "✗",      # Cross mark  
            "⚠️": "!",      # Warning sign
            "📊": "[DATA]", # Chart
            "🔄": "↻",      # Arrows
            "💰": "$",      # Money bag
            "📈": "↗",      # Trending up
            "📉": "↘",      # Trending down
        }

        for unicode_char, ascii_replacement in unicode_map.items():
            text = text.replace(unicode_char, ascii_replacement)

        return text


class ErrorLocationFilter(logging.Filter):
    """Filter that adds detailed error location information only for WARNING and higher"""
    
    def filter(self, record):
        # Only add detailed location info for WARNING and higher
        if record.levelno >= logging.WARNING:
            try:
                # Get the calling frame
                frame = sys._getframe()
                
                # Walk up the call stack to find the actual caller
                # Skip logging-related frames and __init__.py files
                skip_files = {'logger.py', 'logging', '__init__.py'}
                
                while frame:
                    filename = Path(frame.f_code.co_filename).name
                    if not any(skip in filename for skip in skip_files):
                        break
                    frame = frame.f_back
                
                if frame:
                    # Add enhanced location information
                    full_path = Path(frame.f_code.co_filename)
                    try:
                        relative_path = full_path.relative_to(Path.cwd())
                        record.caller_file = str(relative_path)
                        
                        # Handle __init__.py files specially
                        if full_path.name == '__init__.py':
                            record.caller_filename = relative_path.parent.name
                        else:
                            record.caller_filename = relative_path.name
                            
                    except ValueError:
                        record.caller_file = str(full_path)
                        if full_path.name == '__init__.py':
                            record.caller_filename = full_path.parent.name
                        else:
                            record.caller_filename = full_path.name
                    
                    record.caller_function = frame.f_code.co_name
                    record.caller_line = frame.f_lineno
                    
            except (AttributeError, ValueError, OSError):
                # Fallback values if inspection fails
                record.caller_file = "unknown"
                record.caller_filename = "unknown"
                record.caller_function = "unknown"
                record.caller_line = 0
        
        return True


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """
    Setup enhanced logging with detailed error location tracking
    
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

    # Create enhanced formatters
    console_formatter = DetailedFormatter(include_colors=True)
    file_formatter = DetailedFormatter(include_colors=False)

    # Console handler with enhanced features
    if sys.platform.startswith("win"):
        console_handler = EnhancedUnicodeHandler()
    else:
        console_handler = logging.StreamHandler()
        console_handler.addFilter(ErrorLocationFilter())

    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with enhanced logging
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_file_size,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, config.level.upper(), logging.DEBUG))
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(ErrorLocationFilter())
        root_logger.addHandler(file_handler)
        
    except Exception as e:
        console_handler.setLevel(logging.DEBUG)
        root_logger.error(f"Failed to setup file logging: {e}")

    _ROOT_LOGGER_SETUP = True
    
    # Return the main application logger
    return get_logger(_APP_NAME)


def get_logger(name: str, module_path: Optional[str] = None) -> logging.Logger:
    """
    Get a standardized logger for a module with enhanced error tracking
    
    Args:
        name: Logger name (typically __name__ or module identifier)
        module_path: Optional module path for better identification
        
    Returns:
        Configured logger instance with enhanced error tracking
        
    Example:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        
        # Enhanced error logging with location info
        try:
            risky_operation()
        except Exception as e:
            logger.error(f"Operation failed: {e}", exc_info=True)
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
            clean_name = name.lstrip(".")
            logger_name = f"{_APP_NAME}.{clean_name}"
    
    # Check if logger already exists in registry
    if logger_name in _LOGGER_REGISTRY:
        return _LOGGER_REGISTRY[logger_name]
    
    # Create new logger
    logger = logging.getLogger(logger_name)
    
    # Store in registry
    _LOGGER_REGISTRY[logger_name] = logger
    
    return logger


def log_exception(logger: logging.Logger, exception: Exception, context: str = "", 
                  include_locals: bool = False) -> None:
    """
    Enhanced exception logging with detailed context and optional local variables
    
    Args:
        logger: Logger instance to use
        exception: Exception that occurred
        context: Additional context about where/when error occurred
        include_locals: Whether to include local variables in the log
        
    Example:
        from utils.logger import get_logger, log_exception
        
        logger = get_logger(__name__)
        
        try:
            result = process_data(data)
        except Exception as e:
            log_exception(logger, e, "processing user data", include_locals=True)
    """
    # Get current frame to extract local variables
    frame = sys._getframe(1)  # Get caller's frame
    
    error_details = {
        'error_type': type(exception).__name__,
        'error_message': str(exception),
        'context': context,
    }
    
    # Add file location information
    if frame:
        file_path = Path(frame.f_code.co_filename)
        try:
            relative_path = file_path.relative_to(Path.cwd())
            error_details['file'] = str(relative_path)
        except ValueError:
            error_details['file'] = file_path.name
            
        error_details['function'] = frame.f_code.co_name
        error_details['line'] = frame.f_lineno
    
    # Include local variables if requested
    if include_locals and frame:
        local_vars = {}
        for var_name, var_value in frame.f_locals.items():
            try:
                # Safely convert to string, avoiding large objects
                if isinstance(var_value, (str, int, float, bool, type(None))):
                    local_vars[var_name] = var_value
                else:
                    local_vars[var_name] = f"<{type(var_value).__name__}>"
            except Exception:
                local_vars[var_name] = "<unprintable>"
        
        error_details['local_variables'] = local_vars
    
    # Format the error message
    context_str = f" in {context}" if context else ""
    location_str = ""
    if 'file' in error_details:
        location_str = f" [{error_details['file']}:{error_details['function']}:{error_details['line']}]"
    
    error_msg = f"{error_details['error_type']}{context_str}{location_str}: {error_details['error_message']}"
    
    # Log with full exception info
    logger.error(error_msg, exc_info=True, extra=error_details)


def setup_debug_logging() -> logging.Logger:
    """
    Setup debug-level logging with maximum detail for troubleshooting
    
    Returns:
        Logger configured for debug output with detailed formatting
    """
    # Create debug logger
    debug_logger = logging.getLogger(f"{_APP_NAME}.debug")
    debug_logger.setLevel(logging.DEBUG)
    
    # Create detailed formatter for debug
    debug_formatter = DetailedFormatter(include_location=True, include_colors=True)
    
    # Console handler for debug
    debug_handler = logging.StreamHandler(sys.stdout)
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(debug_formatter)
    debug_handler.addFilter(ErrorLocationFilter())
    
    debug_logger.addHandler(debug_handler)
    
    return debug_logger


def get_logger_with_context(name: str, **context) -> logging.Logger:
    """
    Get a logger with additional context information
    
    Args:
        name: Logger name
        **context: Additional context to include in all log messages
        
    Returns:
        Logger with context filter applied
        
    Example:
        logger = get_logger_with_context(__name__, user_id="123", operation="data_sync")
        logger.info("Starting process")  # Will include user_id and operation in log
    """
    logger = get_logger(name)
    
    # Create a filter to add context
    class ContextFilter(logging.Filter):
        def __init__(self, context_data):
            self.context_data = context_data
            super().__init__()
        
        def filter(self, record):
            for key, value in self.context_data.items():
                setattr(record, key, value)
            return True
    
    logger.addFilter(ContextFilter(context))
    return logger


# Convenience functions for backward compatibility
def setup_module_logger(module_name: str) -> logging.Logger:
    """DEPRECATED: Use get_logger() instead"""
    import warnings
    warnings.warn(
        "setup_module_logger is deprecated, use get_logger() instead",
        DeprecationWarning,
        stacklevel=2
    )
    return get_logger(module_name)


def list_registered_loggers() -> Dict[str, str]:
    """List all registered loggers for debugging"""
    return {
        name: logging.getLevelName(logger.getEffectiveLevel())
        for name, logger in _LOGGER_REGISTRY.items()
    }