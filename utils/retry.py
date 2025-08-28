# ./utils/retry.py

"""
Retry logic with exponential backoff for Robinhood Crypto Trading App
"""

# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring

import time
from utils.logger import get_logger
from typing import Callable, Any, Type, Tuple
from functools import wraps

logger = get_logger("crypto_app.retry")


def retry_with_backoff(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for retrying functions with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries
        initial_delay: Initial delay in seconds
        exceptions: Tuple of exception types to catch and retry
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        # Last attempt, don't wait
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts. "
                            f"Final error: {str(e)}"
                        )
                        break

                    # Calculate delay for next attempt
                    delay = initial_delay * (backoff_factor**attempt)

                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}/{max_attempts}. "
                        f"Error: {str(e)}. Retrying in {delay:.2f} seconds..."
                    )

                    time.sleep(delay)

            # If we get here, all attempts failed
            raise last_exception

        return wrapper

    return decorator


class RetryConfig:
    """Configuration class for retry behavior"""

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_factor: float = 2.0,
        initial_delay: float = 1.0,
    ):
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.initial_delay = initial_delay

    def apply_to(self, exceptions: Tuple[Type[Exception], ...] = (Exception,)):
        """Create a retry decorator with these settings"""
        return retry_with_backoff(
            max_attempts=self.max_attempts,
            backoff_factor=self.backoff_factor,
            initial_delay=self.initial_delay,
            exceptions=exceptions,
        )
