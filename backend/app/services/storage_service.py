"""Storage service factory and org-scoped path enforcement."""

from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from app.core.config import Settings, get_settings
from app.services.storage.azure import AzureBlobStorageBackend
from app.services.storage.base import StorageBackend
from app.services.storage.filesystem import FilesystemStorageBackend


class ConfigurationError(Exception):
    """Raised when storage configuration is invalid."""


def create_storage_backend(settings: Settings | None = None) -> StorageBackend:
    """Instantiate the configured storage backend."""
    cfg = settings or get_settings()
    backend = cfg.STORAGE_BACKEND

    if backend == "filesystem":
        return FilesystemStorageBackend(cfg.STORAGE_LOCAL_PATH)
    if backend == "azure":
        return AzureBlobStorageBackend(
            container=cfg.AZURE_CONTAINER_NAME,
            connection_string=cfg.AZURE_STORAGE_CONNECTION_STRING,
            account_name=cfg.AZURE_STORAGE_ACCOUNT_NAME,
            sas_token=cfg.AZURE_STORAGE_SAS_TOKEN,
        )

    raise ConfigurationError(
        f"Unknown STORAGE_BACKEND '{backend}'. "
        "Expected one of: filesystem, azure."
    )


class StorageService:
    """Org-scoped storage facade used by upload and submission services."""

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self._backend = backend or create_storage_backend()

    @staticmethod
    def normalize_path(path: str) -> str:
        return path.lstrip("/").replace("\\", "/")

    @classmethod
    def org_prefix(cls, organization_id: UUID) -> str:
        return f"org/{organization_id}"

    @classmethod
    def ensure_org_prefix(cls, path: str, organization_id: UUID) -> str:
        """Ensure all writes are scoped under org/{organization_id}/."""
        normalized = cls.normalize_path(path)
        required = f"{cls.org_prefix(organization_id)}/"
        if normalized.startswith(required):
            return normalized
        if normalized.startswith(f"{cls.org_prefix(organization_id)}"):
            return normalized if normalized.endswith("/") else normalized
        return f"{required}{normalized}"

    def put(self, path: str, data: bytes, *, organization_id: UUID) -> str:
        key = self.ensure_org_prefix(path, organization_id)
        self._backend.put(key, data)
        return key

    def put_bytes(self, path: str, data: bytes) -> None:
        """Write to an already org-scoped storage key."""
        self._backend.put(self.normalize_path(path), data)

    def get(self, path: str) -> bytes:
        return self._backend.get(self.normalize_path(path))

    def delete(self, path: str) -> None:
        self._backend.delete(self.normalize_path(path))

    def exists(self, path: str) -> bool:
        return self._backend.exists(self.normalize_path(path))


@lru_cache
def get_storage_service() -> StorageService:
    return StorageService()
