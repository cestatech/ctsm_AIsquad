"""Pluggable storage backends for artifact and submission file I/O."""

from app.services.storage.azure import AzureBlobStorageBackend
from app.services.storage.base import StorageBackend
from app.services.storage.filesystem import FilesystemStorageBackend
from app.services.storage.s3 import S3StorageBackend

__all__ = [
    "AzureBlobStorageBackend",
    "FilesystemStorageBackend",
    "S3StorageBackend",
    "StorageBackend",
]
