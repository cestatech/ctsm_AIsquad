"""Repository for AI decisions, human overrides, data lineage, and validation evidence.

All queries are org-scoped. This layer never accepts tenant context from user input.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import (
    AIDecision,
    AIDecisionStatus,
    ArtifactLineage,
    DataLineage,
    HumanOverride,
    SimulationAssumption,
    SyntheticDataRun,
    ValidationEvidence,
    ValidationEvidenceStatus,
)


class AIDecisionRepository:
    """Database access for AI decision records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, decision_id: UUID, organization_id: UUID) -> AIDecision:
        result = await self._db.execute(
            select(AIDecision).where(
                AIDecision.id == decision_id,
                AIDecision.organization_id == organization_id,
            )
        )
        decision = result.scalar_one_or_none()
        if decision is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "AI decision not found."},
            )
        return decision

    async def create(self, decision: AIDecision) -> AIDecision:
        self._db.add(decision)
        await self._db.flush()
        await self._db.refresh(decision)
        return decision

    async def list_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        agent_name: str | None = None,
        decision_type: str | None = None,
        status: AIDecisionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AIDecision], int]:
        filters = [
            AIDecision.study_id == study_id,
            AIDecision.organization_id == organization_id,
        ]
        if agent_name is not None:
            filters.append(AIDecision.agent_name == agent_name)
        if decision_type is not None:
            filters.append(AIDecision.decision_type == decision_type)
        if status is not None:
            filters.append(AIDecision.status == status)

        count_result = await self._db.execute(
            select(AIDecision).where(and_(*filters))
        )
        total = len(count_result.scalars().all())

        result = await self._db.execute(
            select(AIDecision)
            .where(and_(*filters))
            .order_by(AIDecision.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def update_status(
        self,
        decision_id: UUID,
        organization_id: UUID,
        new_status: AIDecisionStatus,
        reviewed_by_id: UUID,
        review_notes: str | None = None,
    ) -> AIDecision:
        from datetime import datetime, timezone

        decision = await self.get(decision_id, organization_id)
        decision.status = new_status
        decision.reviewed_by_id = reviewed_by_id
        decision.reviewed_at = datetime.now(timezone.utc)
        if review_notes is not None:
            decision.review_notes = review_notes
        await self._db.flush()
        return decision

    async def pending_for_org(
        self,
        organization_id: UUID,
        limit: int = 50,
    ) -> list[AIDecision]:
        result = await self._db.execute(
            select(AIDecision)
            .where(
                AIDecision.organization_id == organization_id,
                AIDecision.status == AIDecisionStatus.PENDING_REVIEW,
            )
            .order_by(AIDecision.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


class HumanOverrideRepository:
    """Database access for human override records. Append-only."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, override: HumanOverride) -> HumanOverride:
        self._db.add(override)
        await self._db.flush()
        await self._db.refresh(override)
        return override

    async def list_for_decision(
        self,
        ai_decision_id: UUID,
        organization_id: UUID,
    ) -> list[HumanOverride]:
        result = await self._db.execute(
            select(HumanOverride).where(
                HumanOverride.ai_decision_id == ai_decision_id,
                HumanOverride.organization_id == organization_id,
            ).order_by(HumanOverride.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        context_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[HumanOverride], int]:
        filters = [
            HumanOverride.study_id == study_id,
            HumanOverride.organization_id == organization_id,
        ]
        if context_type is not None:
            filters.append(HumanOverride.context_type == context_type)

        count_result = await self._db.execute(
            select(HumanOverride).where(and_(*filters))
        )
        total = len(count_result.scalars().all())

        result = await self._db.execute(
            select(HumanOverride)
            .where(and_(*filters))
            .order_by(HumanOverride.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total


class DataLineageRepository:
    """Database access for data and artifact lineage records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, lineage: DataLineage) -> DataLineage:
        self._db.add(lineage)
        await self._db.flush()
        await self._db.refresh(lineage)
        return lineage

    async def create_artifact_lineage(self, link: ArtifactLineage) -> ArtifactLineage:
        self._db.add(link)
        await self._db.flush()
        await self._db.refresh(link)
        return link

    async def lineage_chain_for_target(
        self,
        target_type: str,
        target_id: UUID,
        organization_id: UUID,
    ) -> list[DataLineage]:
        """All lineage records where this entity is the target (its upstream sources)."""
        result = await self._db.execute(
            select(DataLineage).where(
                DataLineage.target_type == target_type,
                DataLineage.target_id == target_id,
                DataLineage.organization_id == organization_id,
                DataLineage.is_active.is_(True),
            ).order_by(DataLineage.created_at.asc())
        )
        return list(result.scalars().all())

    async def lineage_chain_for_source(
        self,
        source_type: str,
        source_id: UUID,
        organization_id: UUID,
    ) -> list[DataLineage]:
        """All lineage records where this entity is the source (its downstream derivations)."""
        result = await self._db.execute(
            select(DataLineage).where(
                DataLineage.source_type == source_type,
                DataLineage.source_id == source_id,
                DataLineage.organization_id == organization_id,
                DataLineage.is_active.is_(True),
            ).order_by(DataLineage.created_at.asc())
        )
        return list(result.scalars().all())

    async def artifact_lineage_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
    ) -> list[ArtifactLineage]:
        result = await self._db.execute(
            select(ArtifactLineage).where(
                ArtifactLineage.study_id == study_id,
                ArtifactLineage.organization_id == organization_id,
            ).order_by(ArtifactLineage.created_at.asc())
        )
        return list(result.scalars().all())


class ValidationEvidenceRepository:
    """Database access for validation evidence records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, evidence: ValidationEvidence) -> ValidationEvidence:
        self._db.add(evidence)
        await self._db.flush()
        await self._db.refresh(evidence)
        return evidence

    async def list_for_run(
        self,
        validation_run_id: UUID,
        organization_id: UUID,
        evidence_status: ValidationEvidenceStatus | None = None,
    ) -> list[ValidationEvidence]:
        filters = [
            ValidationEvidence.validation_run_id == validation_run_id,
            ValidationEvidence.organization_id == organization_id,
        ]
        if evidence_status is not None:
            filters.append(ValidationEvidence.status == evidence_status)

        result = await self._db.execute(
            select(ValidationEvidence)
            .where(and_(*filters))
            .order_by(ValidationEvidence.finding_severity.asc(),
                      ValidationEvidence.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        evidence_status: ValidationEvidenceStatus | None = None,
        rule_category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ValidationEvidence], int]:
        filters = [
            ValidationEvidence.study_id == study_id,
            ValidationEvidence.organization_id == organization_id,
        ]
        if evidence_status is not None:
            filters.append(ValidationEvidence.status == evidence_status)
        if rule_category is not None:
            filters.append(ValidationEvidence.rule_category == rule_category)

        count_result = await self._db.execute(
            select(ValidationEvidence).where(and_(*filters))
        )
        total = len(count_result.scalars().all())

        result = await self._db.execute(
            select(ValidationEvidence)
            .where(and_(*filters))
            .order_by(ValidationEvidence.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def waive(
        self,
        evidence_id: UUID,
        organization_id: UUID,
        waived_by_id: UUID,
        reason: str,
    ) -> ValidationEvidence:
        from datetime import datetime, timezone

        result = await self._db.execute(
            select(ValidationEvidence).where(
                ValidationEvidence.id == evidence_id,
                ValidationEvidence.organization_id == organization_id,
            )
        )
        evidence = result.scalar_one_or_none()
        if evidence is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Validation evidence not found."},
            )
        evidence.status = ValidationEvidenceStatus.WAIVED
        evidence.waived_by_id = waived_by_id
        evidence.waiver_reason = reason
        evidence.waived_at = datetime.now(timezone.utc)
        await self._db.flush()
        return evidence


class SyntheticDataRepository:
    """Database access for synthetic data runs and simulation assumptions."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_run(self, run: SyntheticDataRun) -> SyntheticDataRun:
        self._db.add(run)
        await self._db.flush()
        await self._db.refresh(run)
        return run

    async def create_assumption(self, assumption: SimulationAssumption) -> SimulationAssumption:
        self._db.add(assumption)
        await self._db.flush()
        await self._db.refresh(assumption)
        return assumption

    async def get_run(self, run_id: UUID, organization_id: UUID) -> SyntheticDataRun:
        result = await self._db.execute(
            select(SyntheticDataRun).where(
                SyntheticDataRun.id == run_id,
                SyntheticDataRun.organization_id == organization_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Synthetic data run not found."},
            )
        return run

    async def list_runs_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SyntheticDataRun], int]:
        filters = [
            SyntheticDataRun.study_id == study_id,
            SyntheticDataRun.organization_id == organization_id,
        ]

        count_result = await self._db.execute(
            select(SyntheticDataRun).where(and_(*filters))
        )
        total = len(count_result.scalars().all())

        result = await self._db.execute(
            select(SyntheticDataRun)
            .where(and_(*filters))
            .order_by(SyntheticDataRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total
