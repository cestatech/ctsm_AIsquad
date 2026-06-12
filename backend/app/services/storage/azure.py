"""Azure Blob Storage backend."""

from __future__ import annotations

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

from app.services.storage.base import StorageBackend


class AzureBlobStorageBackend(StorageBackend):
    """Store objects in an Azure Blob Storage container."""

    def __init__(
        self,
        *,
        container: str,
        connection_string: str = "",
        account_name: str = "",
        sas_token: str = "",
        client: BlobServiceClient | None = None,
    ) -> None:
        if not container:
            raise ValueError("AZURE_CONTAINER_NAME is required for Azure storage.")
        self._container = container
        if client is not None:
            self._client = client
        elif connection_string:
            self._client = BlobServiceClient.from_connection_string(connection_string)
        elif account_name and sas_token:
            account_url = f"https://{account_name}.blob.core.windows.net"
            self._client = BlobServiceClient(
                account_url=account_url,
                credential=sas_token,
            )
        else:
            raise ValueError(
                "Azure storage requires AZURE_STORAGE_CONNECTION_STRING or "
                "AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_SAS_TOKEN."
            )

    def _blob_name(self, path: str) -> str:
        return path.lstrip("/").replace("\\", "/")

    def _blob_client(self, path: str):
        return self._client.get_blob_client(
            container=self._container,
            blob=self._blob_name(path),
        )

    def put(self, path: str, data: bytes) -> None:
        self._blob_client(path).upload_blob(data, overwrite=True)

    def get(self, path: str) -> bytes:
        downloader = self._blob_client(path).download_blob()
        return downloader.readall()

    def delete(self, path: str) -> None:
        self._blob_client(path).delete_blob()

    def exists(self, path: str) -> bool:
        try:
            self._blob_client(path).get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
