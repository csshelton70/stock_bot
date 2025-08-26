"""
Robinhood Crypto API Exception Classes Module
============================================

This module defines custom exception classes for handling various types of errors
that can occur when interacting with the Robinhood Crypto API. These exceptions
provide structured error handling with additional context about API responses.

Classes:
    RobinhoodAPIError: Base exception for all Robinhood API errors
    RobinhoodAuthError: Authentication and authorization errors
    RobinhoodRateLimitError: Rate limiting and quota exceeded errors
    RobinhoodValidationError: Request validation and parameter errors
    RobinhoodServerError: Server-side errors (5xx responses)

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

from typing import Dict, Optional, Any


class RobinhoodAPIError(Exception):
    """
    Base exception class for all Robinhood API errors.

    This is the parent class for all API-related exceptions and provides
    common functionality for error handling, including status codes and
    response data preservation.

    Attributes:
        message (str): Human-readable error message
        status_code (Optional[int]): HTTP status code from the API response
        response_data (Optional[Dict]): Raw response data from the API
        request_id (Optional[str]): Request ID for tracking (if available)
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the API error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code from the response
            response_data: Raw response data from the API
            request_id: Request ID for tracking purposes
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        self.request_id = request_id

    def __str__(self) -> str:
        """
        Return a formatted string representation of the error.

        Returns:
            str: Formatted error message with additional context
        """
        error_parts = [self.message]

        if self.status_code:
            error_parts.append(f"Status Code: {self.status_code}")

        if self.request_id:
            error_parts.append(f"Request ID: {self.request_id}")

        if self.response_data and isinstance(self.response_data, dict):
            if "errors" in self.response_data:
                errors = self.response_data["errors"]
                if isinstance(errors, list) and errors:
                    error_details = []
                    for error in errors:
                        if isinstance(error, dict):
                            detail = error.get("detail", "")
                            attr = error.get("attr", "")
                            if attr and attr != "non_field_errors":
                                error_details.append(f"{attr}: {detail}")
                            else:
                                error_details.append(detail)
                    if error_details:
                        error_parts.append(f"Details: {'; '.join(error_details)}")

        return " | ".join(error_parts)

    def get_error_details(self) -> list:
        """
        Extract detailed error information from the response.

        Returns:
            list: List of error detail dictionaries
        """
        if not self.response_data or not isinstance(self.response_data, dict):
            return []

        errors = self.response_data.get("errors", [])
        if not isinstance(errors, list):
            return []

        return errors

    def has_field_errors(self) -> bool:
        """
        Check if the error contains field-specific validation errors.

        Returns:
            bool: True if there are field-specific errors
        """
        errors = self.get_error_details()
        return any(
            isinstance(error, dict)
            and error.get("attr")
            and error.get("attr") != "non_field_errors"
            for error in errors
        )


class RobinhoodAuthError(RobinhoodAPIError):
    """
    Authentication and authorization related errors.

    This exception is raised when there are issues with API authentication,
    such as invalid API keys, expired tokens, or insufficient permissions.

    Common scenarios:
    - Invalid API key
    - Invalid signature
    - Expired timestamp
    - Insufficient permissions
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the authentication error.

        Args:
            message: Error message (defaults to generic auth message)
            status_code: HTTP status code
            response_data: API response data
            request_id: Request tracking ID
        """
        super().__init__(message, status_code, response_data, request_id)


class RobinhoodRateLimitError(RobinhoodAPIError):
    """
    Rate limiting and quota exceeded errors.

    This exception is raised when the API rate limits are exceeded.
    It includes information about retry timing when available.

    Common scenarios:
    - Too many requests per minute
    - Burst limit exceeded
    - Daily quota exceeded

    Note: This library does not implement client-side rate limiting.
    Rate limiting should be handled by the application or by respecting
    the API's built-in rate limiting mechanisms.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        """
        Initialize the rate limit error.

        Args:
            message: Error message
            status_code: HTTP status code
            response_data: API response data
            request_id: Request tracking ID
            retry_after: Seconds to wait before retrying (from Retry-After header)
        """
        super().__init__(message, status_code, response_data, request_id)
        self.retry_after = retry_after

    def __str__(self) -> str:
        """
        Return formatted string with retry information.

        Returns:
            str: Formatted error message including retry timing
        """
        base_str = super().__str__()
        if self.retry_after:
            base_str += f" | Retry after: {self.retry_after} seconds"
        return base_str


class RobinhoodValidationError(RobinhoodAPIError):
    """
    Request validation and parameter errors.

    This exception is raised when the API request contains invalid parameters,
    missing required fields, or fails validation rules.

    Common scenarios:
    - Invalid order parameters
    - Missing required fields
    - Invalid symbol format
    - Invalid quantity values
    """

    def __init__(
        self,
        message: str = "Request validation failed",
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the validation error.

        Args:
            message: Error message
            status_code: HTTP status code
            response_data: API response data
            request_id: Request tracking ID
        """
        super().__init__(message, status_code, response_data, request_id)

    def get_field_errors(self) -> Dict[str, str]:
        """
        Extract field-specific validation errors.

        Returns:
            Dict[str, str]: Mapping of field names to error messages
        """
        field_errors = {}
        for error in self.get_error_details():
            if isinstance(error, dict):
                attr = error.get("attr")
                detail = error.get("detail", "")
                if attr and attr != "non_field_errors":
                    field_errors[attr] = detail
        return field_errors


class RobinhoodServerError(RobinhoodAPIError):
    """
    Server-side errors (5xx HTTP responses).

    This exception is raised when the Robinhood API experiences internal
    server errors, maintenance periods, or other server-side issues.

    Common scenarios:
    - Internal server error (500)
    - Service unavailable (503)
    - Gateway timeout (504)
    - Maintenance mode
    """

    def __init__(
        self,
        message: str = "Server error occurred",
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the server error.

        Args:
            message: Error message
            status_code: HTTP status code
            response_data: API response data
            request_id: Request tracking ID
        """
        super().__init__(message, status_code, response_data, request_id)

    @property
    def is_retryable(self) -> bool:
        """
        Check if this server error is potentially retryable.

        Returns:
            bool: True if the error might be resolved by retrying
        """
        # 500, 502, 503, 504 are typically retryable
        retryable_codes = {500, 502, 503, 504}
        return self.status_code in retryable_codes if self.status_code else True


# Utility functions for error handling
def create_error_from_response(
    response_status: int,
    response_data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> RobinhoodAPIError:
    """
    Create appropriate error instance based on HTTP status code.

    Args:
        response_status: HTTP status code
        response_data: API response data
        request_id: Request tracking ID

    Returns:
        RobinhoodAPIError: Appropriate error subclass instance
    """
    message = f"API request failed with status {response_status}"

    if response_status == 401:
        return RobinhoodAuthError(message, response_status, response_data, request_id)
    elif response_status == 429:
        retry_after = None
        if response_data and isinstance(response_data, dict):
            # Look for retry-after information in response
            retry_after = response_data.get("retry_after")
        return RobinhoodRateLimitError(
            message, response_status, response_data, request_id, retry_after
        )
    elif response_status == 400:
        return RobinhoodValidationError(
            message, response_status, response_data, request_id
        )
    elif response_status >= 500:
        return RobinhoodServerError(message, response_status, response_data, request_id)
    else:
        return RobinhoodAPIError(message, response_status, response_data, request_id)


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error is retryable.

    Args:
        error: Exception to check

    Returns:
        bool: True if the error might be resolved by retrying
    """
    if isinstance(error, RobinhoodServerError):
        return error.is_retryable
    elif isinstance(error, RobinhoodRateLimitError):
        return True
    elif isinstance(error, (RobinhoodAuthError, RobinhoodValidationError)):
        return False
    else:
        return False
