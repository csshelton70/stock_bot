# data/repositories/base_repository.py
"""
Base repository pattern implementation
Provides common database operations with proper error handling and transactions
"""

# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation

# Standard Imports
from utils.logger import get_logger
from contextlib import contextmanager

from abc import ABC
from typing import List, Optional, TypeVar, Generic, Type, Any
from sqlalchemy.exc import SQLAlchemyError

from data.connections.database_session import DatabaseManager

T = TypeVar("T")


class BaseRepository(Generic[T], ABC):
    """Enhanced base repository with session management utilities"""

    def __init__(self, db_manager: DatabaseManager, model_class: Type[T]):
        self.db_manager = db_manager
        self.model_class = model_class
        self.logger = get_logger(f"repositories.{self.__class__.__name__.lower()}")

    @contextmanager
    def get_session(self):
        """Get database session with automatic cleanup"""
        session = self.db_manager.get_session()
        try:
            yield session
            session.commit()  # type:ignore
        except Exception as e:
            session.rollback()  # type:ignore
            self.logger.error(f"Database operation failed: {e}")
            raise
        finally:
            session.close()  # type:ignore

    def create(self, entity: T) -> T:
        """Create new entity"""
        with self.get_session() as session:
            session.add(entity)  # type:ignore
            session.flush()  # type:ignore
            session.refresh(entity)  # type:ignore
            # Detach from session to avoid binding issues
            session.expunge(entity)  # type:ignore
            return entity

    def get_by_id(self, entity_id: Any) -> Optional[T]:
        """Get entity by ID - returns detached object"""
        with self.get_session() as session:
            entity = session.query(self.model_class).get(entity_id)  # type:ignore
            if entity:
                session.expunge(entity)  # type:ignore # Detach from session
            return entity

    def update(self, entity: T) -> T:
        """Update existing entity"""
        with self.get_session() as session:
            merged = session.merge(entity)  # type:ignore
            session.flush()  # type:ignore
            session.refresh(merged)  # type:ignore
            session.expunge(merged)  # type:ignore # Detach from session
            return merged

    def delete(self, entity: T) -> bool:
        """Delete entity"""
        try:
            with self.get_session() as session:
                # Re-attach to session for deletion
                session.merge(entity)  # type:ignore
                session.delete(entity)  # type:ignore
                return True
        except SQLAlchemyError:
            return False

    def get_all(self, limit: Optional[int] = None) -> List[T]:
        """Get all entities with optional limit - returns detached objects"""
        with self.get_session() as session:
            query = session.query(self.model_class)  # type:ignore
            if limit:
                query = query.limit(limit)
            entities = query.all()

            # Detach all entities from session
            for entity in entities:
                session.expunge(entity)  # type:ignore

            return entities

    def execute_in_session(self, operation_func):
        """
        Execute a custom operation within a managed session.

        Args:
            operation_func: Function that takes a session as parameter

        Returns:
            Result of the operation function
        """
        with self.get_session() as session:
            return operation_func(session)
