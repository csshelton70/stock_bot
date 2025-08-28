"""
Robinhood Crypto API Base Client Module
======================================

This module provides the base API client with authentication, request handling,
and common functionality shared across all API modules.

Classes:
    RobinhoodBaseClient: Base client with authentication and request handling

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

import base64
import datetime
import json
import logging
from utils.logger import get_logger
from typing import Any, Dict, Optional

import requests
from nacl.signing import SigningKey
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .robinhood_config import RobinhoodConfig
from .robinhood_error import (
    RobinhoodAuthError,
    RobinhoodAPIError,
    create_error_from_response,
)

# pylint:disable = raise-missing-from,logging-fstring-interpolation,broad-exception-caught


class RobinhoodBaseClient:
    """
    Base Robinhood Crypto API client with authentication and request handling.

    This class provides the fundamental functionality for making authenticated
    requests to the Robinhood Crypto API. It handles authentication, request
    signing, error handling, and retry mechanisms.

    Attributes:
        config (RobinhoodConfig): Configuration settings
        private_key (SigningKey): Private key for request signing
        session (requests.Session): HTTP session with retry configuration
        logger (logging.Logger): Logger instance for debugging
    """

    def __init__(self, config: Optional[RobinhoodConfig] = None) -> None:
        """
        Initialize the base API client.

        Args:
            config: Configuration object. If None, loads from environment variables.

        Raises:
            RobinhoodAuthError: If API key or private key are missing
            ValueError: If configuration validation fails
        """
        self.config = config or RobinhoodConfig.from_env()

        # Validate configuration
        if not self.config.api_key or not self.config.private_key_base64:
            raise RobinhoodAuthError("API key and private key must be provided")

        # Setup logging
        self._setup_logging()

        # Initialize authentication
        try:
            private_key_seed = base64.b64decode(self.config.private_key_base64)
            self.private_key = SigningKey(private_key_seed)
        except Exception as e:
            raise RobinhoodAuthError(f"Invalid private key format: {e}")

        # Setup HTTP session with retries
        self.session = self._create_session()

        self.logger.info("RobinhoodBaseClient initialized successfully")

    def _setup_logging(self) -> None:
        # Setup logging configuration using centralized system
        self.logger = get_logger("robinhood.api_client")
        self.logger.debug("Robinhood API client logger initialized")
        # That's it! No need to create additional handlers
        # The centralized logging system already handles everything

    def _create_session(self) -> requests.Session:
        """
        Create HTTP session with retry strategy.

        Returns:
            requests.Session: Configured session with retry strategy
        """
        session = requests.Session()

        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _get_current_timestamp(self) -> int:
        """
        Get current Unix timestamp.

        Returns:
            int: Current Unix timestamp in seconds
        """
        return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

    def _get_authorization_headers(
        self, method: str, path: str, body: str = ""
    ) -> Dict[str, str]:
        """
        Generate authorization headers for API requests.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            body: Request body as string

        Returns:
            Dict[str, str]: Authorization headers including signature
        """
        timestamp = self._get_current_timestamp()
        message_to_sign = f"{self.config.api_key}{timestamp}{path}{method}{body}"
        signed = self.private_key.sign(message_to_sign.encode("utf-8"))

        return {
            "x-api-key": self.config.api_key,
            "x-signature": base64.b64encode(signed.signature).decode("utf-8"),
            "x-timestamp": str(timestamp),
            "Content-Type": "application/json; charset=utf-8",
        }

    def _handle_response(self, response: requests.Response) -> Any:
        """
        Handle API response and errors.

        Args:
            response: HTTP response object

        Returns:
            Any: Parsed JSON response or response text

        Raises:
            Various RobinhoodAPIError subclasses based on error type
        """
        self.logger.debug(f"Response status: {response.status_code}")

        # Handle successful responses
        if 200 <= response.status_code < 300:
            try:
                return response.json() if response.content else {}
            except json.JSONDecodeError:
                return response.text

        # Handle error responses
        try:
            error_data = response.json()
        except json.JSONDecodeError:
            error_data = {"detail": response.text}

        # Extract request ID if available
        request_id = response.headers.get("x-request-id")

        # Create appropriate error based on status code
        error = create_error_from_response(response.status_code, error_data, request_id)
        raise error

    def make_request(self, method: str, path: str, body: Optional[Dict] = None) -> Any:
        """
        Make authenticated API request with error handling.

        Args:
            method: HTTP method
            path: API endpoint path
            body: Request body dictionary

        Returns:
            Any: API response data

        Raises:
            Various RobinhoodAPIError subclasses based on error conditions
        """
        body_str = json.dumps(body) if body else ""
        headers = self._get_authorization_headers(method, path, body_str)
        url = self.config.base_url + path

        self.logger.debug(f"Making {method} request to {path}")

        try:
            if method.upper() == "GET":
                response = self.session.get(
                    url, headers=headers, timeout=self.config.request_timeout
                )
            elif method.upper() == "POST":
                response = self.session.post(
                    url, headers=headers, json=body, timeout=self.config.request_timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            return self._handle_response(response)

        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise RobinhoodAPIError(f"Network error: {e}")

    def close(self) -> None:
        """Close the HTTP session."""
        if hasattr(self, "session"):
            self.session.close()
            self.logger.info("HTTP session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def health_check(self) -> bool:
        """
        Perform a basic health check by making a simple API request.

        Returns:
            bool: True if the API is accessible and authentication works
        """
        try:
            # Make a simple request to test connectivity
            self.make_request("GET", "/api/v1/crypto/trading/accounts/")
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
