"""Upload service — store files and extract metadata.

Supports CSV and XLSX (column header extraction) and generic binary files.
Every upload creates an audit log entry per CLAUDE.md requirements.
"""

from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.audit import AuditAction
from app.models.upload import UploadedFile
from app.models.user import User
from app.repositories.study_repository import StudyRepository
from app.repositories.upload_repository import UploadRepository
from app.services.audit_service import AuditService

_ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
    "text/plain",
}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


class UploadService:
    """Handles file storage and metadata extraction for study uploads."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = UploadRepository(db)
        self._study_repo = StudyRepository(db)
        self._audit = AuditService(db)
        self._settings = get_settings()

    async def upload_file(
        self,
        study_id: UUID,
        actor: User,
        file: UploadFile,
        description: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UploadedFile:
        """Store a file for a study and record its metadata."""
        await self._study_repo.get(study_id, actor.organization_id)

        content = await file.read()
        if len(content) > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"code": "FILE_TOO_LARGE", "message": "File exceeds 50 MB limit."},
            )

        mime_type = file.content_type or "application/octet-stream"
        if mime_type not in _ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "code": "UNSUPPORTED_MEDIA_TYPE",
                    "message": f"File type '{mime_type}' is not allowed. Supported: CSV, XLSX, PDF, TXT.",
                },
            )

        stored_filename = f"{uuid.uuid4()}_{file.filename or 'upload'}"
        org_prefix = Path(self._settings.STORAGE_LOCAL_PATH) / "org" / str(actor.organization_id) / "studies" / str(study_id) / "uploads"
        org_prefix.mkdir(parents=True, exist_ok=True)
        file_path = org_prefix / stored_filename
        file_path.write_bytes(content)

        extracted_metadata = self._extract_metadata(content, mime_type, file.filename or "")

        record = await self._repo.create(
            organization_id=actor.organization_id,
            study_id=study_id,
            uploaded_by_id=actor.id,
            original_filename=file.filename or stored_filename,
            stored_filename=stored_filename,
            file_path=str(file_path),
            file_size_bytes=len(content),
            mime_type=mime_type,
            description=description,
            extracted_metadata=extracted_metadata,
        )

        await self._audit.log(
            action=AuditAction.STUDY_UPDATED,
            resource_type="uploaded_file",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=record.id,
            after_state={
                "study_id": str(study_id),
                "filename": file.filename,
                "mime_type": mime_type,
                "size_bytes": len(content),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._db.commit()
        return record

    async def list_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[UploadedFile], int]:
        """Return paginated file list for a study."""
        offset = (page - 1) * page_size
        return await self._repo.list_for_study(
            study_id=study_id,
            organization_id=organization_id,
            limit=page_size,
            offset=offset,
        )

    @staticmethod
    def _extract_metadata(content: bytes, mime_type: str, filename: str) -> dict:
        """Extract column headers and row count from CSV files."""
        if mime_type == "text/csv" or filename.lower().endswith(".csv"):
            try:
                text = content.decode("utf-8", errors="replace")
                reader = csv.reader(io.StringIO(text))
                rows = list(reader)
                if rows:
                    return {
                        "columns": rows[0],
                        "row_count": len(rows) - 1,
                        "format": "csv",
                    }
            except Exception:
                pass
        return {"format": mime_type}
