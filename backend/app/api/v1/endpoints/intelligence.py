"""Intelligence API endpoints — AI decisions, human overrides, lineage, validation evidence.

These endpoints surface the explainability layer to the frontend and to
external tools. Every AI-generated output has a corresponding AI decision
accessible here. Every human correction creates a human override record.

Permissions (RBAC enforced in service layer):
  - AI decisions: read = any authenticated user; review = ADMIN or REVIEWER
  - Human overrides: create = any authenticated user; read = any
  - Lineage: read = any authenticated user
  - Validation evidence: read = any; waive = ADMIN or REVIEWER
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.permissions import Permission, check_permission
from app.models.intelligence import AIDecisionStatus, ValidationEvidenceStatus
from app.models.user import User
from app.schemas.intelligence import (
    AIDecisionListResponse,
    AIDecisionResponse,
    CreateOverrideRequest,
    DataLineageResponse,
    HumanOverrideListResponse,
    HumanOverrideResponse,
    LineageChainResponse,
    RejectDecisionRequest,
    ReviewDecisionRequest,
    ValidationEvidenceListResponse,
    ValidationEvidenceResponse,
    WaiveFindingRequest,
)
from app.repositories.intelligence_repository import SyntheticDataRunRepository
from app.schemas.intelligence import SyntheticDataRunListResponse, SyntheticDataRunResponse
from app.services.intelligence_service import (
    AIDecisionService,
    DataLineageService,
    HumanOverrideService,
    ValidationIntelligenceService,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# AI Decisions
# ---------------------------------------------------------------------------


@router.get(
    "/decisions",
    response_model=AIDecisionListResponse,
    summary="List AI decisions for a study",
)
async def list_decisions(
    study_id: UUID = Query(..., description="Study ID to scope the query"),
    agent_name: str | None = Query(None),
    decision_type: str | None = Query(None),
    decision_status: AIDecisionStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIDecisionListResponse:
    """
    List AI decision records for a study, with optional filters.

    Returns the full provenance record for each AI action:
    which agent, which model, what input, what output, current review status.
    """
    svc = AIDecisionService(db)
    offset = (page - 1) * page_size
    decisions, total = await svc.list_for_study(
        study_id=study_id,
        organization_id=current_user.organization_id,
        agent_name=agent_name,
        decision_type=decision_type,
        decision_status=decision_status,
        limit=page_size,
        offset=offset,
    )
    return AIDecisionListResponse(
        items=[AIDecisionResponse.model_validate(d) for d in decisions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/decisions/pending",
    response_model=list[AIDecisionResponse],
    summary="List pending AI decisions awaiting human review",
)
async def list_pending_decisions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AIDecisionResponse]:
    """
    Return all AI decisions with PENDING_REVIEW status for the organization.

    Used by the AI Decision Review screen to surface items awaiting human approval.
    """
    svc = AIDecisionService(db)
    decisions = await svc.list_pending(current_user.organization_id)
    return [AIDecisionResponse.model_validate(d) for d in decisions]


@router.get(
    "/decisions/{decision_id}",
    response_model=AIDecisionResponse,
    summary="Get a single AI decision",
)
async def get_decision(
    decision_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIDecisionResponse:
    """Fetch the full provenance record for a single AI decision."""
    svc = AIDecisionService(db)
    decision = await svc.get_decision(decision_id, current_user.organization_id)
    return AIDecisionResponse.model_validate(decision)


@router.post(
    "/decisions/{decision_id}/accept",
    response_model=AIDecisionResponse,
    summary="Accept an AI decision",
)
async def accept_decision(
    decision_id: UUID,
    body: ReviewDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIDecisionResponse:
    """
    Accept an AI decision. Transitions status to ACCEPTED.

    Requires REVIEWER or ADMIN role.
    Optional review notes are stored on the decision record.
    """
    check_permission(current_user, Permission.ARTIFACT_APPROVE)
    svc = AIDecisionService(db)
    decision = await svc.accept_decision(
        decision_id=decision_id,
        organization_id=current_user.organization_id,
        reviewed_by=current_user,
        notes=body.notes,
    )
    return AIDecisionResponse.model_validate(decision)


@router.post(
    "/decisions/{decision_id}/reject",
    response_model=AIDecisionResponse,
    summary="Reject an AI decision",
)
async def reject_decision(
    decision_id: UUID,
    body: RejectDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIDecisionResponse:
    """
    Reject an AI decision. Transitions status to REJECTED.

    Requires REVIEWER or ADMIN role. Rejection notes are mandatory.
    """
    check_permission(current_user, Permission.ARTIFACT_REJECT)
    svc = AIDecisionService(db)
    decision = await svc.reject_decision(
        decision_id=decision_id,
        organization_id=current_user.organization_id,
        reviewed_by=current_user,
        notes=body.notes,
    )
    return AIDecisionResponse.model_validate(decision)


# ---------------------------------------------------------------------------
# Human Overrides
# ---------------------------------------------------------------------------


@router.post(
    "/overrides",
    response_model=HumanOverrideResponse,
    status_code=201,
    summary="Record a human override of an AI-generated value",
)
async def create_override(
    body: CreateOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HumanOverrideResponse:
    """
    Record an immutable human override event.

    Call this whenever a user edits a value that was AI-generated.
    A justification (reason) is mandatory for all overrides.
    The record is append-only and cannot be deleted.
    """
    svc = HumanOverrideService(db)
    override = await svc.record_override(
        organization_id=current_user.organization_id,
        actor=current_user,
        context_type=body.context_type,
        original_value=body.original_value,
        new_value=body.new_value,
        reason=body.reason,
        override_type=body.override_type,
        study_id=body.study_id,
        ai_decision_id=body.ai_decision_id,
        context_id=body.context_id,
        field_path=body.field_path,
        graph_node_id=body.graph_node_id,
    )
    return HumanOverrideResponse.model_validate(override)


@router.get(
    "/overrides",
    response_model=HumanOverrideListResponse,
    summary="List human overrides for a study",
)
async def list_overrides(
    study_id: UUID = Query(...),
    context_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HumanOverrideListResponse:
    """List all human override records for a study, optionally filtered by context_type."""
    svc = HumanOverrideService(db)
    offset = (page - 1) * page_size
    overrides, total = await svc.list_for_study(
        study_id=study_id,
        organization_id=current_user.organization_id,
        context_type=context_type,
        limit=page_size,
        offset=offset,
    )
    return HumanOverrideListResponse(
        items=[HumanOverrideResponse.model_validate(o) for o in overrides],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/overrides/for-decision/{decision_id}",
    response_model=list[HumanOverrideResponse],
    summary="List overrides for a specific AI decision",
)
async def list_overrides_for_decision(
    decision_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[HumanOverrideResponse]:
    """All human overrides that reference a specific AI decision."""
    svc = HumanOverrideService(db)
    overrides = await svc.list_for_decision(decision_id, current_user.organization_id)
    return [HumanOverrideResponse.model_validate(o) for o in overrides]


# ---------------------------------------------------------------------------
# Data Lineage
# ---------------------------------------------------------------------------


@router.get(
    "/lineage/chain",
    response_model=LineageChainResponse,
    summary="Get the data lineage chain for a specific entity",
)
async def get_lineage_chain(
    target_type: str = Query(..., description="Entity type, e.g. 'sdtm_variable'"),
    target_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LineageChainResponse:
    """
    Return the full data lineage chain for a specific entity.

    upstream: all lineage records where this entity is the target (its sources)
    downstream: all lineage records where this entity is the source (its derivations)
    """
    svc = DataLineageService(db)
    upstream = await svc.get_upstream_lineage(
        target_type=target_type,
        target_id=target_id,
        organization_id=current_user.organization_id,
    )
    downstream = await svc.get_downstream_lineage(
        source_type=target_type,
        source_id=target_id,
        organization_id=current_user.organization_id,
    )
    return LineageChainResponse(
        upstream=[DataLineageResponse.model_validate(rec) for rec in upstream],
        downstream=[DataLineageResponse.model_validate(rec) for rec in downstream],
    )


# ---------------------------------------------------------------------------
# Validation Evidence
# ---------------------------------------------------------------------------


@router.get(
    "/validation-evidence",
    response_model=ValidationEvidenceListResponse,
    summary="List validation evidence for a study",
)
async def list_validation_evidence(
    study_id: UUID = Query(...),
    evidence_status: ValidationEvidenceStatus | None = Query(None),
    rule_category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationEvidenceListResponse:
    """
    List validation evidence records for a study.

    Optionally filter by status (PENDING, PASS, FAIL, WARNING, WAIVED)
    and rule_category. Returns paginated results.
    """
    check_permission(current_user, Permission.VALIDATION_RUN)
    svc = ValidationIntelligenceService(db)
    offset = (page - 1) * page_size
    evidence_list, total = await svc.list_for_study(
        study_id=study_id,
        organization_id=current_user.organization_id,
        evidence_status=evidence_status,
        rule_category=rule_category,
        limit=page_size,
        offset=offset,
    )
    return ValidationEvidenceListResponse(
        items=[ValidationEvidenceResponse.model_validate(e) for e in evidence_list],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/validation-evidence/{evidence_id}/waive",
    response_model=ValidationEvidenceResponse,
    summary="Waive a validation finding",
)
async def waive_finding(
    evidence_id: UUID,
    body: WaiveFindingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationEvidenceResponse:
    """
    Waive a validation finding with a mandatory justification.

    Requires ADMIN or REVIEWER role. The waiver reason is stored on the
    evidence record and is available in the regulatory submission package.
    """
    check_permission(current_user, Permission.ARTIFACT_APPROVE)
    svc = ValidationIntelligenceService(db)
    evidence = await svc.waive_finding(
        evidence_id=evidence_id,
        organization_id=current_user.organization_id,
        waived_by=current_user,
        reason=body.reason,
    )
    return ValidationEvidenceResponse.model_validate(evidence)


# ---------------------------------------------------------------------------
# Synthetic Data Runs
# ---------------------------------------------------------------------------


@router.get(
    "/synthetic-runs",
    response_model=SyntheticDataRunListResponse,
    summary="List synthetic data runs for a study",
)
async def list_synthetic_runs(
    study_id: UUID = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyntheticDataRunListResponse:
    """List all synthetic data runs for a study, newest first."""
    repo = SyntheticDataRunRepository(db)
    offset = (page - 1) * page_size
    runs, total = await repo.list_for_study(
        study_id=study_id,
        organization_id=current_user.organization_id,
        limit=page_size,
        offset=offset,
    )
    return SyntheticDataRunListResponse(
        items=[SyntheticDataRunResponse.model_validate(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )
