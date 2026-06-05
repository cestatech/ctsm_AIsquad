"""Upload service — store files, parse structure, profile columns, register CIP graph.

Phase 2 additions:
  - SHA-256 file hash (immutability + duplicate detection)
  - CSV and XLSX parsing into RawDataset + RawField records
  - Column profiling: inferred type, sample values, missing/distinct counts, min/max
  - CIP context graph registration: UploadedFile, RawDataset, RawField nodes + edges
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.audit import AuditAction
from app.models.graph import GraphEdgeType, GraphNodeType
from app.models.upload import UploadedFile
from app.models.user import User
from app.repositories.raw_data_repository import RawDatasetRepository, RawFieldRepository
from app.repositories.study_repository import StudyRepository
from app.repositories.upload_repository import UploadRepository
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService

_ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
    "text/plain",
}
_PARSEABLE_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
_MAX_PROFILE_ROWS = 10_000        # cap profiling scan to avoid OOM


class UploadService:
    """Handles file storage, parsing, profiling, and CIP graph registration."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = UploadRepository(db)
        self._study_repo = StudyRepository(db)
        self._audit = AuditService(db)
        self._ds_repo = RawDatasetRepository(db)
        self._field_repo = RawFieldRepository(db)
        self._graph = ContextGraphService(db)
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
        """Store a file, parse/profile its columns, and register in the CIP graph."""
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

        file_hash = hashlib.sha256(content).hexdigest()
        stored_filename = f"{uuid.uuid4()}_{file.filename or 'upload'}"
        org_prefix = (
            Path(self._settings.STORAGE_LOCAL_PATH)
            / "org"
            / str(actor.organization_id)
            / "studies"
            / str(study_id)
            / "uploads"
        )
        org_prefix.mkdir(parents=True, exist_ok=True)
        file_path = org_prefix / stored_filename
        file_path.write_bytes(content)

        extracted_metadata = self._extract_legacy_metadata(content, mime_type, file.filename or "")

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
            file_hash=file_hash,
            upload_status="UPLOADED",
        )

        await self._audit.log(
            action=AuditAction.DATA_FILE_UPLOADED,
            resource_type="uploaded_file",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=record.id,
            after_state={
                "study_id": str(study_id),
                "filename": file.filename,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "file_hash": file_hash,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Parse and profile if it's a structured file
        if mime_type in _PARSEABLE_MIME_TYPES or (file.filename or "").lower().endswith(".csv"):
            await self._parse_and_profile(
                record=record,
                content=content,
                mime_type=mime_type,
                filename=file.filename or "",
                actor=actor,
                study_id=study_id,
            )

        await self._db.commit()
        return record

    async def _parse_and_profile(
        self,
        record: UploadedFile,
        content: bytes,
        mime_type: str,
        filename: str,
        actor: User,
        study_id: UUID,
    ) -> None:
        """Parse file into sheets/columns, profile each column, register graph."""
        try:
            sheets = self._parse_file(content, mime_type, filename)
            record.upload_status = "PARSED"

            # Register UploadedFile node in the CIP graph
            file_node, _ = await self._graph.register_domain_record(
                organization_id=actor.organization_id,
                node_type=GraphNodeType.UPLOADED_FILE,
                external_id=record.id,
                external_type="uploaded_file",
                label=record.original_filename,
                study_id=study_id,
                actor=actor,
            )

            # Get the Study graph node (for the belongs_to edge)
            study_node, _ = await self._graph.register_domain_record(
                organization_id=actor.organization_id,
                node_type=GraphNodeType.STUDY,
                external_id=study_id,
                external_type="study",
                label=str(study_id),
                study_id=study_id,
                actor=actor,
            )

            await self._graph.create_relationship(
                organization_id=actor.organization_id,
                source_node_id=file_node.id,
                target_node_id=study_node.id,
                edge_type=GraphEdgeType.PART_OF,
                study_id=study_id,
                actor=actor,
            )

            for sheet in sheets:
                ds = await self._ds_repo.create(
                    organization_id=actor.organization_id,
                    study_id=study_id,
                    uploaded_file_id=record.id,
                    dataset_name=sheet["name"],
                    row_count=sheet["row_count"],
                    column_count=len(sheet["columns"]),
                    parse_status="PARSED",
                )

                ds_node, _ = await self._graph.register_domain_record(
                    organization_id=actor.organization_id,
                    node_type=GraphNodeType.RAW_DATASET,
                    external_id=ds.id,
                    external_type="raw_dataset",
                    label=f"{record.original_filename} / {sheet['name']}",
                    study_id=study_id,
                    actor=actor,
                )

                await self._graph.create_relationship(
                    organization_id=actor.organization_id,
                    source_node_id=ds_node.id,
                    target_node_id=file_node.id,
                    edge_type=GraphEdgeType.DERIVED_FROM,
                    study_id=study_id,
                    actor=actor,
                )

                for col in sheet["columns"]:
                    field = await self._field_repo.create(
                        organization_id=actor.organization_id,
                        study_id=study_id,
                        raw_dataset_id=ds.id,
                        column_name=col["name"],
                        column_index=col["index"],
                        inferred_type=col["inferred_type"],
                        sample_values=col["sample_values"],
                        missing_count=col["missing_count"],
                        distinct_count=col["distinct_count"],
                        min_value=col.get("min_value"),
                        max_value=col.get("max_value"),
                    )

                    field_node, _ = await self._graph.register_domain_record(
                        organization_id=actor.organization_id,
                        node_type=GraphNodeType.RAW_DATA_FIELD,
                        external_id=field.id,
                        external_type="raw_field",
                        label=col["name"],
                        study_id=study_id,
                        actor=actor,
                    )

                    await self._graph.create_relationship(
                        organization_id=actor.organization_id,
                        source_node_id=field_node.id,
                        target_node_id=ds_node.id,
                        edge_type=GraphEdgeType.PART_OF,
                        study_id=study_id,
                        actor=actor,
                    )

        except Exception as exc:
            record.upload_status = "FAILED"
            record.extracted_metadata = {
                **record.extracted_metadata,
                "parse_error": str(exc),
            }

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

    async def get_file(
        self, file_id: UUID, organization_id: UUID
    ) -> UploadedFile:
        """Return a single file record; raise 404 if not found."""
        record = await self._repo.get_by_id(file_id, organization_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Upload not found."},
            )
        return record

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_file(content: bytes, mime_type: str, filename: str) -> list[dict]:
        """Return a list of sheet dicts, each with name, row_count, and columns."""
        fn_lower = filename.lower()
        if mime_type == "text/csv" or fn_lower.endswith(".csv"):
            return UploadService._parse_csv(content, filename)
        if mime_type in (
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ) or fn_lower.endswith((".xlsx", ".xls")):
            return UploadService._parse_xlsx(content)
        return []

    @staticmethod
    def _parse_csv(content: bytes, filename: str) -> list[dict]:
        text = content.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return []
        headers = rows[0]
        data_rows = rows[1:_MAX_PROFILE_ROWS]
        columns = []
        for col_idx, header in enumerate(headers):
            col_vals = []
            for row in data_rows:
                col_vals.append(row[col_idx] if col_idx < len(row) else None)
            columns.append(
                {"name": header or f"col_{col_idx}", "index": col_idx,
                 **UploadService._profile_column(col_vals)}
            )
        return [{"name": filename, "row_count": len(data_rows), "columns": columns}]

    @staticmethod
    def _parse_xlsx(content: bytes) -> list[dict]:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        sheets = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.values)
            if not rows:
                continue
            headers = [
                str(h) if h is not None else f"col_{i}"
                for i, h in enumerate(rows[0])
            ]
            data_rows = rows[1:_MAX_PROFILE_ROWS]
            columns = []
            for col_idx, header in enumerate(headers):
                col_vals = [
                    str(row[col_idx]) if (col_idx < len(row) and row[col_idx] is not None) else None
                    for row in data_rows
                ]
                columns.append(
                    {"name": header, "index": col_idx,
                     **UploadService._profile_column(col_vals)}
                )
            sheets.append(
                {"name": sheet_name, "row_count": len(data_rows), "columns": columns}
            )
        wb.close()
        return sheets

    @staticmethod
    def _profile_column(values: list[str | None]) -> dict:
        """Compute profiling stats for a single column's raw string values."""
        non_null = [v for v in values if v is not None and v != ""]
        sample = non_null[:5]
        missing = sum(1 for v in values if v is None or v == "")
        distinct = len(set(non_null))

        inferred_type = "string"
        probe = non_null[:50]
        if probe:
            if all(_try_float(v) is not None for v in probe):
                inferred_type = "number"
            elif all(_try_date(v) for v in probe):
                inferred_type = "date"
            elif all(v.strip().lower() in ("true", "false", "yes", "no", "1", "0") for v in probe):
                inferred_type = "boolean"

        min_val = max_val = None
        if inferred_type == "number" and non_null:
            try:
                nums = [float(v) for v in non_null]
                min_val = str(min(nums))
                max_val = str(max(nums))
            except Exception:
                pass

        return {
            "sample_values": sample,
            "missing_count": missing,
            "distinct_count": distinct,
            "inferred_type": inferred_type,
            "min_value": min_val,
            "max_value": max_val,
        }

    @staticmethod
    def _extract_legacy_metadata(content: bytes, mime_type: str, filename: str) -> dict:
        """Backward-compatible metadata for the extracted_metadata column."""
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


def _try_float(v: str) -> float | None:
    try:
        return float(v.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _try_date(v: str) -> bool:
    from datetime import datetime as _dt
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"):
        try:
            _dt.strptime(v.strip(), fmt)
            return True
        except (ValueError, AttributeError):
            pass
    return False
