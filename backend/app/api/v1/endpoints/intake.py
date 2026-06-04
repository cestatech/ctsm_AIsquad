"""Sponsor Intake API — AI-driven conversational study information gathering."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.intake import (
    IntakeRespondRequest,
    IntakeResponse,
    StartIntakeResponse,
    StudyBriefResponse,
)
from app.services.intake_service import IntakeService

router = APIRouter()


@router.post(
    "",
    response_model=StartIntakeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a sponsor intake session",
)
async def start_intake(
    study_id: UUID = Query(..., description="Study to run the intake for"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartIntakeResponse:
    """
    Create a new intake session for the given study.

    The AI immediately generates a greeting and first question.
    Returns 409 if an active session already exists for this study.
    """
    svc = IntakeService(db)
    intake = await svc.start_session(
        study_id=study_id,
        organization_id=current_user.organization_id,
        actor=current_user,
    )
    return StartIntakeResponse(intake=IntakeResponse.model_validate(intake))


@router.get(
    "/{intake_id}",
    response_model=IntakeResponse,
    summary="Get intake session with messages",
)
async def get_intake(
    intake_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntakeResponse:
    """Return the full intake session with all visible conversation messages."""
    svc = IntakeService(db)
    intake = await svc.get_session(intake_id, current_user.organization_id)
    return IntakeResponse.model_validate(intake)


@router.post(
    "/{intake_id}/respond",
    response_model=IntakeResponse,
    summary="Submit an answer and receive AI follow-up",
)
async def respond_to_intake(
    intake_id: UUID,
    body: IntakeRespondRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntakeResponse:
    """
    Submit the intake officer's response to the current question.

    The AI processes the answer, stores it, generates the next question or
    signals readiness to compile, and returns the updated session.
    """
    svc = IntakeService(db)
    intake = await svc.respond(
        intake_id=intake_id,
        organization_id=current_user.organization_id,
        actor=current_user,
        user_message=body.message,
    )
    return IntakeResponse.model_validate(intake)


@router.post(
    "/{intake_id}/compile",
    response_model=StudyBriefResponse,
    summary="Compile conversation into a Study Brief",
)
async def compile_brief(
    intake_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyBriefResponse:
    """
    Synthesise all collected information into a structured Study Brief JSON.

    The Study Brief is the source of truth for Protocol, ICF, SAP, and all
    downstream generation. This call is idempotent — returns existing brief
    if already compiled.
    """
    svc = IntakeService(db)
    brief = await svc.compile_brief(
        intake_id=intake_id,
        organization_id=current_user.organization_id,
        actor=current_user,
    )
    return StudyBriefResponse.model_validate(brief)


@router.get(
    "/{intake_id}/brief",
    response_model=StudyBriefResponse,
    summary="Retrieve compiled Study Brief",
)
async def get_brief(
    intake_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyBriefResponse:
    """Return the compiled Study Brief. Returns 404 if not yet compiled."""
    svc = IntakeService(db)
    brief = await svc.get_brief(intake_id, current_user.organization_id)
    return StudyBriefResponse.model_validate(brief)


@router.get(
    "",
    response_model=list[IntakeResponse],
    summary="List intake sessions for a study",
)
async def list_intakes(
    study_id: UUID = Query(..., description="Study to list sessions for"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[IntakeResponse]:
    """List all intake sessions for a study, newest first."""
    svc = IntakeService(db)
    intakes = await svc.list_for_study(study_id, current_user.organization_id)
    return [IntakeResponse.model_validate(i) for i in intakes]
