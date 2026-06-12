"""Unit tests for pluggable storage backends and StorageService."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.storage.azure import AzureBlobStorageBackend
from app.services.storage.filesystem import FilesystemStorageBackend
from app.services.storage_service import (
    ConfigurationError,
    StorageService,
    create_storage_backend,
)


class TestFilesystemBackend:
    def test_put_get_delete_exists(self, tmp_path):
        backend = FilesystemStorageBackend(tmp_path)
        key = "org/demo/uploads/sample.csv"
        backend.put(key, b"hello")
        assert backend.exists(key)
        assert backend.get(key) == b"hello"
        backend.delete(key)
        assert not backend.exists(key)


class TestStorageServiceOrgPrefix:
    def test_put_enforces_org_prefix(self, tmp_path):
        org_id = uuid4()
        storage = StorageService(FilesystemStorageBackend(tmp_path))
        key = storage.put(
            "studies/demo/uploads/file.csv",
            b"data",
            organization_id=org_id,
        )
        assert key == f"org/{org_id}/studies/demo/uploads/file.csv"
        assert storage.get(key) == b"data"


class TestStorageFactory:
    def test_filesystem_backend_default(self, tmp_path, monkeypatch):
        settings = Settings(
            APP_SECRET_KEY="test",
            JWT_SECRET_KEY="test",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            STORAGE_BACKEND="filesystem",
            STORAGE_LOCAL_PATH=str(tmp_path),
        )
        backend = create_storage_backend(settings)
        assert isinstance(backend, FilesystemStorageBackend)

    def test_azure_backend(self):
        settings = Settings(
            APP_SECRET_KEY="test",
            JWT_SECRET_KEY="test",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            STORAGE_BACKEND="azure",
            AZURE_CONTAINER_NAME="celerius",
            AZURE_STORAGE_ACCOUNT_NAME="celerius",
            AZURE_STORAGE_SAS_TOKEN="test-token",
        )
        backend = create_storage_backend(settings)
        assert isinstance(backend, AzureBlobStorageBackend)

    def test_s3_backend_is_rejected(self):
        with pytest.raises(ValueError, match="STORAGE_BACKEND"):
            Settings(
                APP_SECRET_KEY="test",
                JWT_SECRET_KEY="test",
                DATABASE_URL="postgresql://user:pass@localhost/db",
                STORAGE_BACKEND="s3",
            )

    def test_unknown_backend_raises_configuration_error(self):
        settings = MagicMock()
        settings.STORAGE_BACKEND = "minio"
        with pytest.raises(
            ConfigurationError,
            match="Expected one of: filesystem, azure",
        ):
            create_storage_backend(settings)


class TestAzureBackend:
    def test_put_get_delete_exists_with_mock_client(self):
        container = "celerius"
        blob_name = "org/demo/uploads/sample.csv"
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value.readall.return_value = b"azure-data"
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.get_blob_client.return_value = mock_blob

        backend = AzureBlobStorageBackend(
            container=container,
            connection_string="UseDevelopmentStorage=true",
            client=mock_client,
        )
        backend.put(blob_name, b"azure-data")
        mock_blob.upload_blob.assert_called_once_with(b"azure-data", overwrite=True)
        assert backend.get(blob_name) == b"azure-data"
        backend.delete(blob_name)
        mock_blob.delete_blob.assert_called_once()
        mock_blob.get_blob_properties.return_value = {}
        assert backend.exists(blob_name)
