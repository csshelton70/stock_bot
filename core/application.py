# core/application.py - Updated dependency registration
"""
Fixed application framework with proper dependency registration
"""

import logging
import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Dict, Any, Optional, Type, TypeVar
from dataclasses import dataclass

from config.settings import AppConfig
from core.dependency_injection import DIContainer
from core.error_handling import ErrorHandler
from utils.logger import setup_logging

T = TypeVar("T")


@dataclass
class ApplicationContext:
    """Application context with shared resources"""

    config: AppConfig
    container: DIContainer
    error_handler: ErrorHandler
    logger: logging.Logger


class BaseApplication(ABC):
    """Base application class with standardized setup, execution, and teardown."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.context: Optional[ApplicationContext] = None
        self._setup_complete = False

    def setup(self) -> None:
        """Setup application components"""
        if self._setup_complete:
            return

        try:
            # Load configuration
            config = AppConfig.load(self.config_path)
            config.validate()

            # Setup logging
            logger = setup_logging(config.logging)
            logger.info(f"=== {self.get_app_name()} Starting ===")

            # Create DI container
            container = DIContainer()
            self._register_dependencies(container, config)

            # Setup error handler
            error_handler = ErrorHandler(logger)

            # Create application context
            self.context = ApplicationContext(
                config=config,
                container=container,
                error_handler=error_handler,
                logger=logger,
            )

            # Custom setup
            self._setup_custom()

            self._setup_complete = True
            self.context.logger.info("Application setup completed successfully")

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(f"Application setup failed: {e}")
            else:
                print(f"Application setup failed: {e}")
            raise

    def run(self) -> int:
        """Run the application with proper error handling and cleanup."""
        exit_code = 0

        try:
            self.setup()

            with self._application_context():
                exit_code = self._run_main()

        except KeyboardInterrupt:
            if self.context:
                self.context.logger.info("Application interrupted by user")
            exit_code = 1
        except Exception as e:
            if self.context:
                self.context.error_handler.handle_critical_error(e)
            else:
                print(f"Critical error during startup: {e}")
            exit_code = 2
        finally:
            self._cleanup()

        return exit_code

    @contextmanager
    def _application_context(self):
        """Context manager for application lifecycle"""
        try:
            self._startup()
            yield
        finally:
            self._shutdown()

    def _register_dependencies(self, container: DIContainer, config: AppConfig) -> None:
        """Register common dependencies - FIXED VERSION"""
        from database.connections import DatabaseManager
        from data.repositories.crypto_repository import CryptoRepository

        # Database Manager - direct instance
        db_manager = DatabaseManager(config.database.path)
        container.register("db_manager", db_manager)

        # Repositories - use factory functions that get dependencies correctly
        def create_crypto_repo():
            return CryptoRepository(container.get("db_manager"))

        container.register("crypto_repo", create_crypto_repo, singleton=True)

        # API Client - only if credentials are available
        if config.robinhood.api_key and config.robinhood.private_key_base64:

            def create_api_client():
                from robinhood import create_client

                return create_client(
                    api_key=config.robinhood.api_key,
                    private_key_base64=config.robinhood.private_key_base64,
                )

            container.register("api_client", create_api_client)

    def _startup(self) -> None:
        """Startup operations"""
        self.context.logger.info("Application starting...")

        # Initialize database
        db_manager = self.context.container.get("db_manager")
        db_manager.create_tables()

        self.context.logger.info("Application startup complete")

    def _shutdown(self) -> None:
        """Shutdown operations"""
        if self.context:
            self.context.logger.info("Application shutting down...")

            # Close database connections
            if self.context.container.has("db_manager"):
                db_manager = self.context.container.get("db_manager")
                if hasattr(db_manager, "close"):
                    db_manager.close()

            # Close API client
            if self.context.container.has("api_client"):
                api_client = self.context.container.get("api_client")
                if hasattr(api_client, "close"):
                    api_client.close()

            self.context.logger.info("Application shutdown complete")

    def _cleanup(self) -> None:
        """Final cleanup operations"""
        pass

    # Abstract methods to be implemented by subclasses

    @abstractmethod
    def get_app_name(self) -> str:
        """Return the application name for logging"""
        pass

    @abstractmethod
    def _setup_custom(self) -> None:
        """Custom setup operations for the specific application"""
        pass

    @abstractmethod
    def _run_main(self) -> int:
        """Main application logic."""
        pass
