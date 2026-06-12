"""AWS S3 storage backend."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from app.services.storage.base import StorageBackend


class S3StorageBackend(StorageBackend):
    """Store objects in an AWS S3 bucket."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str = "us-east-1",
        access_key_id: str = "",
        secret_access_key: str = "",
        client=None,
    ) -> None:
        if not bucket:
            raise ValueError("AWS_S3_BUCKET is required for S3 storage.")
        self._bucket = bucket
        if client is not None:
            self._client = client
        else:
            session_kwargs: dict[str, str] = {"region_name": region}
            if access_key_id and secret_access_key:
                session_kwargs["aws_access_key_id"] = access_key_id
                session_kwargs["aws_secret_access_key"] = secret_access_key
            self._client = boto3.client("s3", **session_kwargs)

    def _key(self, path: str) -> str:
        return path.lstrip("/").replace("\\", "/")

    def put(self, path: str, data: bytes) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=self._key(path),
            Body=data,
        )

    def get(self, path: str) -> bytes:
        response = self._client.get_object(
            Bucket=self._bucket,
            Key=self._key(path),
        )
        return response["Body"].read()

    def delete(self, path: str) -> None:
        self._client.delete_object(
            Bucket=self._bucket,
            Key=self._key(path),
        )

    def exists(self, path: str) -> bool:
        try:
            self._client.head_object(
                Bucket=self._bucket,
                Key=self._key(path),
            )
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
