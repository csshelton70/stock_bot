# core/dependency_injection.py (FINAL FIX - No Deadlock)
"""
Fixed dependency injection container - resolves deadlock issues
"""

from typing import Dict, Any, Callable, TypeVar, Type, Union
import threading

from utils.logger import get_logger
logger = get_logger(__name__)  

T = TypeVar("T")


class DIContainer:
    """Simple dependency injection container with singleton support - No Deadlock Version"""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._singleton_flags: set = set()
        self._lock = (
            threading.RLock()
        )  # Use RLock instead of Lock to allow reentrant calls
        self._resolving: set = set()

    def register(
        self,
        name: str,
        service_or_factory: Union[Any, Callable],
        singleton: bool = False,
    ) -> None:
        """Register a service or factory function."""
        with self._lock:
            if callable(service_or_factory):
                self._factories[name] = service_or_factory
            else:
                self._services[name] = service_or_factory

            if singleton:
                self._singleton_flags.add(name)
                self._singletons[name] = None

    def get(self, name: str) -> Any:
        """Get service by name - deadlock-free version"""
        with self._lock:
            # Check for circular dependencies
            if name in self._resolving:
                raise ValueError(
                    f"Circular dependency detected while resolving '{name}'"
                )

            # Check if it's a singleton
            if name in self._singleton_flags:
                if self._singletons[name] is None:
                    self._resolving.add(name)
                    try:
                        if name in self._factories:
                            self._singletons[name] = self._factories[name]()
                        elif name in self._services:
                            self._singletons[name] = self._services[name]
                        else:
                            raise KeyError(f"Service '{name}' not found")
                    finally:
                        self._resolving.discard(name)

                return self._singletons[name]

            # Regular service (non-singleton)
            if name in self._services:
                return self._services[name]

            # Factory (non-singleton)
            if name in self._factories:
                if name in self._resolving:
                    raise ValueError(
                        f"Circular dependency detected while resolving '{name}'"
                    )

                self._resolving.add(name)
                try:
                    return self._factories[name]()
                finally:
                    self._resolving.discard(name)

            raise KeyError(f"Service '{name}' not found")

    def has(self, name: str) -> bool:
        """Check if service exists"""
        return name in self._services or name in self._factories

    def clear_singletons(self) -> None:
        """Clear all singleton instances"""
        with self._lock:
            for name in self._singleton_flags:
                self._singletons[name] = None
