"""Mapping service — manage raw field → eCRF/SDTM mappings with versioning and approval.

Mapping lifecycle:
  map_field()      → UNMAPPED → PENDING_APPROVAL  (Contributor or Admin)
  approve_mapping() → PENDING_APPROVAL → APPROVED  (Reviewer or Admin)
  reject_mapping()  → PENDING_APPROVAL → REJECTED  (Reviewer or Admin)

Every state change creates an immutable FieldMappingVersion record and a CIP
graph edge (RawField maps_to eCRFField or SDTMVariable).
"""

from __future__ import annotations

import csv
import io
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, check_permission
from app.models.audit import AuditAction
from app.models.graph import GraphEdgeType, GraphNodeType
from app.models.intelligence import DataLineageType
from app.models.raw_data import FieldMappingVersion, RawDataset, RawField
from app.models.user import User
from app.repositories.raw_data_repository import (
    FieldMappingVersionRepository,
    RawDatasetRepository,
    RawFieldRepository,
)
from app.repositories.upload_repository import UploadRepository
from app.schemas.raw_data import MappingValidationResult
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService
from app.services.intelligence_service import DataLineageService


class MappingService:
    """Business logic for raw field mapping, approval, and validation."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._upload_repo = UploadRepository(db)
        self._ds_repo = RawDatasetRepository(db)
        self._field_repo = RawFieldRepository(db)
        self._version_repo = FieldMappingVersionRepository(db)
        self._audit = AuditService(db)
        self._graph = ContextGraphService(db)
        self._lineage = DataLineageService(db)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_dataset(
        self, dataset_id: UUID, organization_id: UUID
    ) -> RawDataset:
        ds = await self._ds_repo.get(dataset_id, organization_id)
        if ds is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Dataset not found."},
            )
        return ds

    async def get_field(
        self, field_id: UUID, organization_id: UUID
    ) -> RawField:
        field = await self._field_repo.get(field_id, organization_id)
        if field is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Field not found."},
            )
        return field

    async def list_fields_for_dataset(
        self, dataset_id: UUID, organization_id: UUID
    ) -> list[RawField]:
        await self.get_dataset(dataset_id, organization_id)
        return await self._field_repo.list_for_dataset(dataset_id, organization_id)

    async def list_versions_for_field(
        self, field_id: UUID, organization_id: UUID
    ) -> list[FieldMappingVersion]:
        await self.get_field(field_id, organization_id)
        return await self._version_repo.list_for_field(field_id, organization_id)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def map_field(
        self,
        field_id: UUID,
        mapped_ecrf_field_id: str | None,
        mapped_sdtm_variable_id: str | None,
        notes: str | None,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
        ai_decision_id: UUID | None = None,
        is_ai_generated: bool = False,
    ) -> RawField:
        """Set or update the eCRF/SDTM mapping for a raw field."""
        check_permission(actor, Permission.ARTIFACT_EDIT)

        field = await self.get_field(field_id, actor.organization_id)

        if not mapped_ecrf_field_id and not mapped_sdtm_variable_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "MAPPING_EMPTY",
                    "message": "At least one of mapped_ecrf_field_id or mapped_sdtm_variable_id must be provided.",
                },
            )

        before_state = {
            "mapped_ecrf_field_id": field.mapped_ecrf_field_id,
            "mapped_sdtm_variable_id": field.mapped_sdtm_variable_id,
            "mapping_status": field.mapping_status,
            "mapping_version": field.mapping_version,
        }

        field.mapped_ecrf_field_id = mapped_ecrf_field_id
        field.mapped_sdtm_variable_id = mapped_sdtm_variable_id
        field.mapping_status = "PENDING_APPROVAL"
        field.mapping_version += 1

        version = await self._version_repo.create(
            organization_id=actor.organization_id,
            raw_field_id=field.id,
            version_number=field.mapping_version,
            mapped_ecrf_field_id=mapped_ecrf_field_id,
            mapped_sdtm_variable_id=mapped_sdtm_variable_id,
            mapping_status="PENDING_APPROVAL",
            changed_by_id=actor.id,
            notes=notes,
        )

        # CIP: register graph edges for mappings
        await self._register_mapping_graph_edges(
            field=field,
            actor=actor,
            ai_decision_id=ai_decision_id,
            is_ai_generated=is_ai_generated,
        )

        await self._record_mapping_lineage(
            field=field,
            actor=actor,
            mapped_ecrf_field_id=mapped_ecrf_field_id,
            mapped_sdtm_variable_id=mapped_sdtm_variable_id,
            ai_decision_id=ai_decision_id,
            is_ai_generated=is_ai_generated,
        )

        await self._audit.log(
            action=AuditAction.DATA_FIELD_MAPPED,
            resource_type="raw_field_mapping",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=field.id,
            before_state=before_state,
            after_state={
                "mapped_ecrf_field_id": mapped_ecrf_field_id,
                "mapped_sdtm_variable_id": mapped_sdtm_variable_id,
                "mapping_status": "PENDING_APPROVAL",
                "mapping_version": field.mapping_version,
                "version_id": str(version.id),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._db.flush()
        await self._db.refresh(field)
        return field

    async def approve_mapping(
        self,
        field_id: UUID,
        notes: str | None,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> RawField:
        """Approve a pending mapping. Requires Reviewer or Admin role."""
        check_permission(actor, Permission.ARTIFACT_APPROVE)

        field = await self.get_field(field_id, actor.organization_id)

        if field.mapping_status != "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NOT_PENDING",
                    "message": f"Field mapping status is '{field.mapping_status}', not PENDING_APPROVAL.",
                },
            )

        field.mapping_status = "APPROVED"

        # Update the latest version record with approval
        versions = await self._version_repo.list_for_field(
            field.id, actor.organization_id
        )
        if versions:
            latest = versions[-1]
            latest.mapping_status = "APPROVED"
            latest.approved_by_id = actor.id

        # CIP: approved_by edge
        field_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.RAW_DATA_FIELD,
            external_id=field.id,
            external_type="raw_field",
            label=field.column_name,
            study_id=field.study_id,
            actor=actor,
        )
        reviewer_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.REVIEWER,
            external_id=actor.id,
            external_type="user",
            label=actor.email,
            actor=actor,
        )
        await self._graph.create_relationship(
            organization_id=actor.organization_id,
            source_node_id=field_node.id,
            target_node_id=reviewer_node.id,
            edge_type=GraphEdgeType.APPROVED_BY,
            study_id=field.study_id,
            actor=actor,
        )

        await self._audit.log(
            action=AuditAction.DATA_MAPPING_APPROVED,
            resource_type="raw_field_mapping_approved",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=field.id,
            before_state={"mapping_status": "PENDING_APPROVAL"},
            after_state={"mapping_status": "APPROVED", "approved_by": str(actor.id)},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._db.flush()
        await self._db.refresh(field)
        return field

    async def reject_mapping(
        self,
        field_id: UUID,
        notes: str | None,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> RawField:
        """Reject a pending mapping. Requires Reviewer or Admin role."""
        check_permission(actor, Permission.ARTIFACT_REJECT)

        field = await self.get_field(field_id, actor.organization_id)

        if field.mapping_status != "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NOT_PENDING",
                    "message": f"Field mapping status is '{field.mapping_status}', not PENDING_APPROVAL.",
                },
            )

        field.mapping_status = "REJECTED"

        versions = await self._version_repo.list_for_field(field.id, actor.organization_id)
        if versions:
            latest = versions[-1]
            latest.mapping_status = "REJECTED"
            latest.approved_by_id = actor.id
            if notes:
                latest.notes = (latest.notes or "") + f"\nRejection note: {notes}"

        await self._audit.log(
            action=AuditAction.STUDY_UPDATED,
            resource_type="raw_field_mapping_rejected",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=field.id,
            before_state={"mapping_status": "PENDING_APPROVAL"},
            after_state={"mapping_status": "REJECTED", "rejected_by": str(actor.id)},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._db.flush()
        return field

    async def bulk_approve_mappings(
        self,
        dataset_id: UUID,
        notes: str | None,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[list[RawField], int]:
        """Approve all PENDING_APPROVAL mappings in a dataset."""
        check_permission(actor, Permission.ARTIFACT_APPROVE)

        fields = await self.list_fields_for_dataset(dataset_id, actor.organization_id)
        pending = [f for f in fields if f.mapping_status == "PENDING_APPROVAL"]
        approved: list[RawField] = []

        for field in pending:
            result = await self.approve_mapping(
                field_id=field.id,
                notes=notes,
                actor=actor,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            approved.append(result)

        if approved:
            await self._audit.log(
                action=AuditAction.DATA_MAPPING_APPROVED,
                resource_type="raw_dataset_bulk_approve",
                organization_id=actor.organization_id,
                actor_user_id=actor.id,
                resource_id=dataset_id,
                after_state={
                    "approved_count": len(approved),
                    "dataset_id": str(dataset_id),
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return approved, len(pending)

    async def export_mappings_csv(
        self, dataset_id: UUID, organization_id: UUID
    ) -> str:
        """Export all field mappings for a dataset as CSV."""
        dataset = await self.get_dataset(dataset_id, organization_id)
        fields = await self._field_repo.list_for_dataset(dataset_id, organization_id)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "dataset_name",
            "column_name",
            "inferred_type",
            "mapped_ecrf_field_id",
            "mapped_sdtm_variable_id",
            "mapping_status",
            "mapping_version",
        ])
        for field in fields:
            writer.writerow([
                dataset.dataset_name,
                field.column_name,
                field.inferred_type,
                field.mapped_ecrf_field_id or "",
                field.mapped_sdtm_variable_id or "",
                field.mapping_status,
                field.mapping_version,
            ])
        return buffer.getvalue()

    async def validate_mapping(
        self, dataset_id: UUID, organization_id: UUID
    ) -> MappingValidationResult:
        """Compute mapping coverage and surface issues for a dataset."""
        await self.get_dataset(dataset_id, organization_id)
        fields = await self._field_repo.list_for_dataset(dataset_id, organization_id)

        total = len(fields)
        mapped = sum(
            1 for f in fields
            if f.mapped_ecrf_field_id or f.mapped_sdtm_variable_id
        )
        approved = sum(1 for f in fields if f.mapping_status == "APPROVED")
        pending = sum(1 for f in fields if f.mapping_status == "PENDING_APPROVAL")
        unmapped = sum(1 for f in fields if f.mapping_status == "UNMAPPED")

        issues: list[str] = []
        for f in fields:
            if f.mapping_status == "UNMAPPED":
                issues.append(f"Column '{f.column_name}' has no mapping.")
            elif f.mapped_ecrf_field_id and not f.mapped_sdtm_variable_id:
                issues.append(
                    f"Column '{f.column_name}' has eCRF mapping but no SDTM variable."
                )

        coverage = round(approved / total * 100, 1) if total else 100.0

        return MappingValidationResult(
            total_fields=total,
            mapped_fields=mapped,
            approved_fields=approved,
            pending_fields=pending,
            unmapped_fields=unmapped,
            coverage_pct=coverage,
            issues=issues,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _register_mapping_graph_edges(
        self,
        field: RawField,
        actor: User,
        ai_decision_id: UUID | None = None,
        is_ai_generated: bool = False,
    ) -> None:
        """Register MAPS_TO graph edges for the field's current mapping targets."""
        field_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.RAW_DATA_FIELD,
            external_id=field.id,
            external_type="raw_field",
            label=field.column_name,
            study_id=field.study_id,
            actor=actor,
        )

        if field.mapped_ecrf_field_id:
            ecrf_node, _ = await self._graph.register_domain_record(
                organization_id=actor.organization_id,
                node_type=GraphNodeType.ECR_FIELD,
                external_id=field.id,  # use field id as proxy — no dedicated ecr_fields table yet
                external_type="ecr_field_name",
                label=field.mapped_ecrf_field_id,
                study_id=field.study_id,
                properties={"ecr_field_name": field.mapped_ecrf_field_id},
                actor=actor,
            )
            await self._graph.create_relationship(
                organization_id=actor.organization_id,
                source_node_id=field_node.id,
                target_node_id=ecrf_node.id,
                edge_type=GraphEdgeType.MAPS_TO,
                study_id=field.study_id,
                is_ai_generated=is_ai_generated,
                ai_decision_id=ai_decision_id,
                actor=actor,
            )

        if field.mapped_sdtm_variable_id:
            sdtm_node, _ = await self._graph.register_domain_record(
                organization_id=actor.organization_id,
                node_type=GraphNodeType.SDTM_VARIABLE,
                external_id=field.id,
                external_type="sdtm_variable_name",
                label=field.mapped_sdtm_variable_id,
                study_id=field.study_id,
                properties={"sdtm_variable_name": field.mapped_sdtm_variable_id},
                actor=actor,
            )
            await self._graph.create_relationship(
                organization_id=actor.organization_id,
                source_node_id=field_node.id,
                target_node_id=sdtm_node.id,
                edge_type=GraphEdgeType.MAPS_TO,
                study_id=field.study_id,
                is_ai_generated=is_ai_generated,
                ai_decision_id=ai_decision_id,
                actor=actor,
            )

    async def _record_mapping_lineage(
        self,
        field: RawField,
        actor: User,
        mapped_ecrf_field_id: str | None,
        mapped_sdtm_variable_id: str | None,
        ai_decision_id: UUID | None = None,
        is_ai_generated: bool = False,
    ) -> None:
        """Record field-level lineage for raw → eCRF/SDTM mapping."""
        logic_prefix = "AI-suggested" if is_ai_generated else "Manual"
        if mapped_ecrf_field_id:
            await self._lineage.record_field_lineage(
                organization_id=actor.organization_id,
                lineage_type=DataLineageType.MAPPED,
                source_type="raw_field",
                source_id=field.id,
                source_field=field.column_name,
                target_type="ecr_field",
                target_field=mapped_ecrf_field_id,
                transformation_logic=f"{logic_prefix} raw column to eCRF field mapping",
                study_id=field.study_id,
                created_by=actor,
                is_ai_generated=is_ai_generated,
                ai_decision_id=ai_decision_id,
            )
        if mapped_sdtm_variable_id:
            await self._lineage.record_field_lineage(
                organization_id=actor.organization_id,
                lineage_type=DataLineageType.MAPPED,
                source_type="raw_field",
                source_id=field.id,
                source_field=field.column_name,
                target_type="sdtm_variable",
                target_field=mapped_sdtm_variable_id,
                transformation_logic=f"{logic_prefix} raw column to SDTM variable mapping",
                study_id=field.study_id,
                created_by=actor,
                is_ai_generated=is_ai_generated,
                ai_decision_id=ai_decision_id,
            )
