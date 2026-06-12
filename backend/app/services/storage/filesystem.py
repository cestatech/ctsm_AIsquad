"""Local filesystem storage backend."""

from __future__ import annotations

from pathlib import Path

from app.services.storage.base import StorageBackend


class FilesystemStorageBackend(StorageBackend):
    """Store objects under a configurable local root directory."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _resolve(self, path: str) -> Path:
        normalized = path.lstrip("/").replace("\\", "/")
        resolved = (self._root / normalized).resolve()
        root_resolved = self._root.resolve()
        if not str(resolved).startswith(str(root_resolved)):
            raise ValueError(f"Storage path escapes root: {path}")
        return resolved

    def put(self, path: str, data: bytes) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def get(self, path: str) -> bytes:
        target = self._resolve(path)
        return target.read_bytes()

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            for child in sorted(target.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
            target.rmdir()

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()
