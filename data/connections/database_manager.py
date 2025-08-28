# ./database/connections.py
"""
Database connection management for Robinhood Crypto Trading App
"""

# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring
from typing import Union

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from utils.logger import get_logger
from data.models.base import Base

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database connections and sessions"""

    def __init__(self, database_path: str):
        self.database_path = database_path
        self.engine = None
        self.session_local = None
        self._setup_database()

    def _setup_database(self):
        """Setup database engine and session factory"""
        # SQLite connection string with optimizations
        connection_string = f"sqlite:///{self.database_path}"

        # Create engine with connection pooling for SQLite
        self.engine = create_engine(
            connection_string,
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False,  # Allow multiple threads
                "timeout": 30,  # Connection timeout
            },
            echo=False,  # Set to True for SQL debug logging
        )

        # Create session factory
        self.session_local = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        logger.info(f"Database engine created for: {self.database_path}")

    def create_tables(self):
        """Create all tables if they don't exist"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise

    def get_session(self) -> Union[Session, None]:
        """Get a new database session"""
        if self.session_local is not None:
            return self.session_local()
        else:
            return None

    def close(self):
        """Close database connections"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")
