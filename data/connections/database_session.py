# ./database/connections.py
"""
Database connection management for Robinhood Crypto Trading App
"""

# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring
from sqlalchemy.orm import  Session

from .database_manager import DatabaseManager

from utils.logger import get_logger


logger = get_logger(__name__)


class DatabaseSession:
    """Context manager for database sessions"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.session = None

    def __enter__(self) -> Session:
        self.session = self.db_manager.get_session()
        return self.session #type:ignore

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type is not None:
                # An exception occurred, rollback the transaction
                self.session.rollback()
                logger.warning("Database transaction rolled back due to exception")
            else:
                # No exception, commit the transaction
                self.session.commit()

            self.session.close()
