"""Abstract storage backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Pluggable object storage backend."""

    @abstractmethod
    def put(self, path: str, data: bytes) -> None:
        """Write bytes to the given storage path."""

    @abstractmethod
    def get(self, path: str) -> bytes:
        """Read bytes from the given storage path."""

    @abstractmethod
    def delete(self, path: str) -> None:
        """Delete the object at the given storage path."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Return True when the object exists at the given storage path."""
