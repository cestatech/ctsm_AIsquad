"""Sponsor intake service — AI-driven conversational study information gathering.

Manages the full lifecycle of a sponsor intake session:
  start_session()   → creates session, logs decision, generates AI greeting + first question
  respond()         → stores user reply, logs decision, generates AI follow-up
  compile_brief()   → logs decision, synthesises conversation into structured Study Brief JSON
  get_session()     → retrieves session with visible messages
  get_brief()       → retrieves compiled brief

CIP compliance:
  Every AI call is bracketed by begin_decision() / complete_decision() so every
  question asked, every inference made, and every compiled field is queryable in
  the Context Graph by decision_id with a full reasoning trace.

  The "why" for each AI turn is stored as `reasoning` in the AIDecision record,
  which is also emitted as an AI_DECISION_COMPLETED graph event payload.
"""

from __future__ import annotations

import json
import re
from uuid import UUID

import anthropic
from anthropic.types import TextBlock
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.permissions import Permission, check_permission
from app.models.graph import GraphEdgeType, GraphNodeType
from app.models.intake import (
    IntakeMessage,
    IntakeStatus,
    SponsorIntake,
    StudyBrief,
)
from app.models.user import User
from app.repositories.study_repository import StudyRepository
from app.services.context_graph_service import ContextGraphService
from app.services.intelligence_service import AIDecisionService

# Haiku is fast enough for per-turn questions; Sonnet is used for compilation
_INTAKE_MODEL = "claude-haiku-4-5-20251001"
_COMPILE_MODEL = "claude-sonnet-4-6"

_AGENT_NAME = "intake-specialist"

_SYSTEM_PROMPT = """You are a clinical trial intake specialist at TrialGenesis, an AI-native clinical trial management platform. Your role is to gather all necessary information from a sponsor's representative through a structured conversation to produce a comprehensive Study Brief.

You must gather information across exactly these 9 domains in order:
1. STUDY_OVERVIEW — Study title, therapeutic area, indication, phase, sponsor name, compound/drug code
2. STUDY_DESIGN — Design type (parallel/crossover/factorial), randomization method, blinding (open/single/double), comparator, treatment duration, number of periods
3. POPULATION — Target population description, inclusion criteria, exclusion criteria, age range, estimated sample size, key demographics
4. ENDPOINTS — Primary endpoint(s) with timepoints and instruments, key secondary endpoints, safety endpoints
5. DRUG_TREATMENT — Drug INN name, dose(s) and units, route of administration, formulation type, dosing regimen and schedule
6. SAFETY — Key safety concerns for this compound/indication, monitoring approach, stopping rules, SAE definitions, any REMS requirements
7. REGULATORY — Regulatory submission regions (FDA/EMA/Health Canada/etc.), IND or CTA status, intended submission type (NDA/BLA/MAA), GCP standard, any special designations (Breakthrough/Fast Track/Orphan)
8. STATISTICAL — Statistical framework (frequentist/Bayesian), primary analysis method, significance level (alpha), multiple testing approach, key subgroup analyses
9. SITES — Number of planned sites, countries and regions, estimated enrollment rate per month, key site selection criteria

RESPONSE FORMAT: You MUST always respond with a JSON object exactly like this:
{
  "message": "Your conversational response to the intake officer",
  "domain": "THE_CURRENT_DOMAIN_YOU_ARE_ASKING_ABOUT",
  "domains_completed": ["LIST_OF_DOMAINS_YOU_HAVE_ENOUGH_INFO_ON"],
  "ready_to_compile": false,
  "reasoning": "One sentence explaining why you chose to ask this specific question or why you moved to the next domain"
}

RULES:
- Be conversational and professional — this person is a clinical operations expert
- Focus on one domain at a time; gather enough detail before moving to the next
- When you have sufficient information for a domain, add it to domains_completed and naturally transition to the next domain
- Ask one or two follow-up questions if an answer is incomplete or unclear
- When ALL 9 domains are in domains_completed, set ready_to_compile to true and let the user know you have everything needed
- Never fabricate information — only record what the sponsor explicitly tells you
- domain should reflect what you are CURRENTLY asking about, not what was just completed
- Keep messages clear and concise — avoid lengthy preambles
- The reasoning field is required — write one clear sentence explaining your decision"""

_COMPILE_SYSTEM_PROMPT = """You are a clinical trial data analyst. Given a complete intake conversation transcript, extract and structure all the information into a comprehensive Study Brief JSON document.

Output ONLY valid JSON with this exact structure (fill in all fields from the conversation; use null for genuinely missing information):
{
  "study_overview": {
    "title": "",
    "therapeutic_area": "",
    "indication": "",
    "phase": "",
    "sponsor": "",
    "compound_code": null
  },
  "study_design": {
    "design_type": "",
    "randomization": "",
    "blinding": "",
    "comparator": null,
    "treatment_duration": "",
    "number_of_periods": 1
  },
  "population": {
    "description": "",
    "inclusion_criteria": [],
    "exclusion_criteria": [],
    "age_range": {"min": 18, "max": null},
    "estimated_sample_size": null
  },
  "endpoints": {
    "primary": [{"name": "", "timepoint": "", "instrument": null}],
    "secondary": [],
    "safety": []
  },
  "drug_treatment": {
    "inn_name": "",
    "doses": [],
    "route": "",
    "formulation": null,
    "regimen": ""
  },
  "safety": {
    "key_concerns": [],
    "monitoring_approach": "",
    "stopping_rules": [],
    "sae_definitions": null,
    "rems_required": false
  },
  "regulatory": {
    "regions": [],
    "ind_cta_status": null,
    "submission_type": null,
    "gcp_standard": "ICH E6(R2)",
    "special_designations": []
  },
  "statistical": {
    "framework": "FREQUENTIST",
    "primary_analysis_method": "",
    "alpha_level": 0.05,
    "multiple_testing_approach": null,
    "key_subgroups": []
  },
  "sites": {
    "planned_sites": null,
    "countries": [],
    "estimated_enrollment_rate_per_month": null,
    "site_selection_criteria": []
  }
}"""

_DOMAIN_ORDER = [
    "STUDY_OVERVIEW",
    "STUDY_DESIGN",
    "POPULATION",
    "ENDPOINTS",
    "DRUG_TREATMENT",
    "SAFETY",
    "REGULATORY",
    "STATISTICAL",
    "SITES",
]

_DOMAIN_QUESTIONS: dict[str, str] = {
    "STUDY_OVERVIEW": (
        "Let's begin with the study overview. Please share the study title, "
        "therapeutic area, indication, phase, sponsor name, and compound/drug code."
    ),
    "STUDY_DESIGN": (
        "Now describe the study design: parallel/crossover/factorial, "
        "randomization method, blinding, comparator, treatment duration, and periods."
    ),
    "POPULATION": (
        "Next, describe the target population: inclusion and exclusion criteria, "
        "age range, estimated sample size, and key demographics."
    ),
    "ENDPOINTS": (
        "What are the primary and key secondary endpoints, including timepoints "
        "and instruments? Include safety endpoints as well."
    ),
    "DRUG_TREATMENT": (
        "Please provide drug/treatment details: INN name, dose(s), route, "
        "formulation, and dosing regimen."
    ),
    "SAFETY": (
        "Describe safety considerations: key concerns, monitoring approach, "
        "stopping rules, SAE definitions, and any REMS requirements."
    ),
    "REGULATORY": (
        "What are the regulatory plans: submission regions, IND/CTA status, "
        "intended submission type, GCP standard, and special designations?"
    ),
    "STATISTICAL": (
        "Outline the statistical framework: frequentist/Bayesian approach, "
        "primary analysis method, alpha level, multiplicity, and key subgroups."
    ),
    "SITES": (
        "Finally, share site plans: number of sites, countries/regions, "
        "estimated enrollment rate per month, and site selection criteria."
    ),
}


class IntakeService:
    """Business logic for sponsor intake sessions with full CIP traceability."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        settings = get_settings()
        self._client = (
            anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            if settings.ANTHROPIC_API_KEY
            else None
        )
        self._study_repo = StudyRepository(db)
        self._ai_decision_svc = AIDecisionService(db)
        self._graph_svc = ContextGraphService(db)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def start_session(
        self, study_id: UUID, organization_id: UUID, actor: User
    ) -> SponsorIntake:
        """
        Create a new intake session and generate the AI opening question.

        CIP: logs an INTAKE_GREETING decision, registers the intake and study
        as graph nodes, and links them before any AI inference runs.
        """
        check_permission(actor, Permission.ARTIFACT_CREATE)
        existing = await self._db.execute(
            select(SponsorIntake).where(
                SponsorIntake.study_id == study_id,
                SponsorIntake.organization_id == organization_id,
                SponsorIntake.status != IntakeStatus.COMPILED,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INTAKE_EXISTS",
                    "message": "An active intake session already exists for this study.",
                },
            )

        study = await self._study_repo.get(study_id, organization_id)

        # CIP: log the decision BEFORE any AI call
        decision = await self._ai_decision_svc.begin_decision(
            organization_id=organization_id,
            agent_name=_AGENT_NAME,
            decision_type="INTAKE_GREETING",
            study_id=study_id,
            model_id=_INTAKE_MODEL,
            input_context={
                "study_name": study.name,
                "study_id": str(study_id),
                "action": "start_intake_session",
            },
        )

        intake = SponsorIntake(
            organization_id=organization_id,
            study_id=study_id,
            created_by_id=actor.id,
            status=IntakeStatus.IN_PROGRESS,
            domains_completed=[],
            ready_to_compile=False,
        )
        self._db.add(intake)
        await self._db.flush()

        # Hidden trigger message — sent to Claude but never shown to user
        trigger = IntakeMessage(
            intake_id=intake.id,
            organization_id=organization_id,
            role="user",
            content=(
                f"Please begin the sponsor intake process for a clinical study called "
                f'"{study.name}". Introduce yourself briefly and ask your first question.'
            ),
            is_hidden=True,
        )
        self._db.add(trigger)
        await self._db.flush()

        # CIP: register intake session as a graph node
        intake_node, _ = await self._graph_svc.register_domain_record(
            organization_id=organization_id,
            node_type=GraphNodeType.INTAKE_SESSION,
            external_id=intake.id,
            external_type="sponsor_intake",
            label=f"Intake: {study.name}",
            study_id=study_id,
            description="AI-driven sponsor intake session",
            properties={"status": "IN_PROGRESS", "domains_completed": []},
            actor=actor,
        )

        # CIP: register study node (idempotent)
        study_node, _ = await self._graph_svc.register_domain_record(
            organization_id=organization_id,
            node_type=GraphNodeType.STUDY,
            external_id=study.id,
            external_type="study",
            label=study.name,
            study_id=study_id,
            actor_agent_id=_AGENT_NAME,
        )

        # CIP: link intake → study
        await self._graph_svc.create_relationship(
            organization_id=organization_id,
            source_node_id=intake_node.id,
            target_node_id=study_node.id,
            edge_type=GraphEdgeType.PART_OF,
            study_id=study_id,
            is_ai_generated=False,
            actor=actor,
        )

        # Call Claude (or deterministic fallback when no API key)
        raw_response = await self._call_claude_conversation(
            messages=[{"role": "user", "content": trigger.content}],
            study_name=study.name,
            is_start=True,
        )
        parsed = self._parse_ai_response(raw_response)

        ai_msg = IntakeMessage(
            intake_id=intake.id,
            organization_id=organization_id,
            role="assistant",
            content=parsed["message"],
            domain=parsed.get("domain"),
            is_hidden=False,
        )
        self._db.add(ai_msg)

        parsed = self._normalize_intake_progress(
            domains_completed=intake.domains_completed,
            parsed=parsed,
        )
        intake.domains_completed = parsed["domains_completed"]
        intake.ready_to_compile = parsed["ready_to_compile"]
        if intake.ready_to_compile:
            intake.status = IntakeStatus.READY_TO_COMPILE

        # CIP: complete decision with reasoning from Claude's own output
        reasoning = parsed.get(
            "reasoning",
            f"Opened intake session, beginning with domain {parsed.get('domain', 'STUDY_OVERVIEW')}",
        )
        await self._ai_decision_svc.complete_decision(
            decision=decision,
            output={
                "message_preview": parsed["message"][:300],
                "domain": parsed.get("domain"),
                "domains_completed": parsed.get("domains_completed", []),
                "ready_to_compile": parsed.get("ready_to_compile", False),
                "intake_id": str(intake.id),
            },
            reasoning=reasoning,
            confidence=1.0,
            graph_node_id=intake_node.id,
        )

        await self._db.commit()
        return await self._load_session(intake.id, organization_id)

    async def respond(
        self,
        intake_id: UUID,
        organization_id: UUID,
        actor: User,
        user_message: str,
    ) -> SponsorIntake:
        """
        Accept a user reply, generate an AI follow-up question.

        CIP: each AI turn is a separate INTAKE_QUESTION decision record that
        captures exactly what the user said, what domain we're covering, which
        domains are now complete, and why Claude chose the next question.
        """
        check_permission(actor, Permission.ARTIFACT_CREATE)
        intake = await self._get_active(intake_id, organization_id)
        visible_messages = [m for m in intake.messages if not m.is_hidden]
        if (
            visible_messages
            and visible_messages[-1].role == "user"
            and visible_messages[-1].content.strip() == user_message.strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_MESSAGE",
                    "message": "This message was already recorded. Wait for the assistant reply.",
                },
            )

        user_msg = IntakeMessage(
            intake_id=intake_id,
            organization_id=organization_id,
            role="user",
            content=user_message,
            is_hidden=False,
        )
        self._db.add(user_msg)
        await self._db.flush()

        # Build history for decision input context
        current_domain = self._current_domain(visible_messages)
        msg_count = len(visible_messages) + 1  # +1 for the message just added

        # CIP: log the decision before calling Claude
        decision = await self._ai_decision_svc.begin_decision(
            organization_id=organization_id,
            agent_name=_AGENT_NAME,
            decision_type="INTAKE_QUESTION",
            study_id=intake.study_id,
            model_id=_INTAKE_MODEL,
            input_context={
                "intake_id": str(intake_id),
                "current_domain": current_domain,
                "domains_completed": intake.domains_completed,
                "domains_remaining": [
                    d
                    for d in [
                        "STUDY_OVERVIEW",
                        "STUDY_DESIGN",
                        "POPULATION",
                        "ENDPOINTS",
                        "DRUG_TREATMENT",
                        "SAFETY",
                        "REGULATORY",
                        "STATISTICAL",
                        "SITES",
                    ]
                    if d not in intake.domains_completed
                ],
                "message_count": msg_count,
                "user_message_preview": user_message[:500],
            },
        )

        # Reconstruct full conversation history (including hidden trigger)
        history_result = await self._db.execute(
            select(IntakeMessage)
            .where(IntakeMessage.intake_id == intake_id)
            .order_by(IntakeMessage.created_at)
        )
        all_messages = list(history_result.scalars().all())
        claude_messages = [{"role": m.role, "content": m.content} for m in all_messages]

        study = await self._study_repo.get(intake.study_id, organization_id)
        raw_response = await self._call_claude_conversation(
            claude_messages,
            study_name=study.name,
            current_domain=current_domain,
            domains_completed=list(intake.domains_completed),
        )
        parsed = self._parse_ai_response(raw_response)
        parsed = self._normalize_intake_progress(
            domains_completed=intake.domains_completed,
            parsed=parsed,
            current_domain=current_domain,
            user_answered=True,
        )

        ai_msg = IntakeMessage(
            intake_id=intake_id,
            organization_id=organization_id,
            role="assistant",
            content=parsed["message"],
            domain=parsed.get("domain"),
            is_hidden=False,
        )
        self._db.add(ai_msg)
        await self._db.flush()

        prior_completed = list(intake.domains_completed)
        intake.domains_completed = parsed["domains_completed"]
        intake.ready_to_compile = parsed["ready_to_compile"]
        if intake.ready_to_compile:
            intake.status = IntakeStatus.READY_TO_COMPILE

        newly_completed = [
            d for d in intake.domains_completed if d not in prior_completed
        ]

        # CIP: complete decision — the reasoning tells the graph exactly WHY
        # Claude asked this next question and what it inferred from the user's answer
        reasoning = parsed.get("reasoning")
        if not reasoning:
            if newly_completed:
                reasoning = (
                    f"Completed domain(s) {newly_completed} based on user's answer; "
                    f"moving to {parsed.get('domain', 'next domain')}"
                )
            else:
                reasoning = (
                    f"Asked follow-up in domain {parsed.get('domain', current_domain)} "
                    f"because more information is needed before moving on"
                )

        await self._ai_decision_svc.complete_decision(
            decision=decision,
            output={
                "message_preview": parsed["message"][:300],
                "domain": parsed.get("domain"),
                "domains_completed": parsed.get("domains_completed", []),
                "newly_completed_domains": newly_completed,
                "ready_to_compile": parsed.get("ready_to_compile", False),
            },
            reasoning=reasoning,
            confidence=1.0,
        )

        # Emit a graph event for each newly completed domain so the graph shows
        # exactly when and why each piece of clinical information was gathered
        for domain in newly_completed:
            await self._graph_svc.emit_event(
                organization_id=organization_id,
                study_id=intake.study_id,
                event_type="INTAKE_DOMAIN_COMPLETED",
                actor_agent_id=_AGENT_NAME,
                ai_decision_id=decision.id,
                payload={
                    "intake_id": str(intake_id),
                    "domain": domain,
                    "completed_at_message_count": msg_count,
                    "reasoning": reasoning,
                },
            )

        await self._db.commit()
        return await self._load_session(intake_id, organization_id)

    async def compile_brief(
        self, intake_id: UUID, organization_id: UUID, actor: User
    ) -> StudyBrief:
        """
        Synthesise all conversation turns into a structured Study Brief.

        CIP: logs a BRIEF_COMPILATION decision that references the full set of
        domains covered and registers the Study Brief as a graph node linked back
        to the intake session. Every field in the brief is traceable to this
        decision record.
        """
        check_permission(actor, Permission.ARTIFACT_CREATE)
        intake = await self._load_session(intake_id, organization_id)

        if intake.status == IntakeStatus.COMPILED and intake.brief:
            return intake.brief

        # Visible messages only for transcript
        history_result = await self._db.execute(
            select(IntakeMessage)
            .where(
                IntakeMessage.intake_id == intake_id,
                IntakeMessage.is_hidden == False,  # noqa: E712
            )
            .order_by(IntakeMessage.created_at)
        )
        visible_messages = list(history_result.scalars().all())
        msg_count = len(visible_messages)

        transcript = "\n\n".join(
            f"[{m.role.upper()}]: {m.content}" for m in visible_messages
        )

        # CIP: log the compilation decision BEFORE calling Claude
        decision = await self._ai_decision_svc.begin_decision(
            organization_id=organization_id,
            agent_name=_AGENT_NAME,
            decision_type="BRIEF_COMPILATION",
            study_id=intake.study_id,
            model_id=_COMPILE_MODEL,
            input_context={
                "intake_id": str(intake_id),
                "domains_covered": intake.domains_completed,
                "message_count": msg_count,
                "action": "compile_study_brief",
            },
        )

        study = await self._study_repo.get(intake.study_id, organization_id)
        if self._client:
            compile_response = await self._client.messages.create(
                model=_COMPILE_MODEL,
                max_tokens=4096,
                system=_COMPILE_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Here is the complete intake conversation transcript. "
                            "Extract and structure all information into the Study Brief JSON:\n\n"
                            + transcript
                        ),
                    }
                ],
            )
            first_block = compile_response.content[0]
            raw = first_block.text if isinstance(first_block, TextBlock) else ""
            brief_content = self._extract_json(raw)
        else:
            domain_answers = self._extract_domain_answers(visible_messages)
            brief_content = self._fallback_brief_content(study, domain_answers)

        brief = StudyBrief(
            intake_id=intake_id,
            organization_id=organization_id,
            study_id=intake.study_id,
            compiled_by_id=actor.id,
            content=brief_content,
        )
        self._db.add(brief)
        await self._db.flush()

        # CIP: register Study Brief as a graph node
        brief_node, _ = await self._graph_svc.register_domain_record(
            organization_id=organization_id,
            node_type=GraphNodeType.STUDY_BRIEF,
            external_id=brief.id,
            external_type="study_brief",
            label=f"Study Brief — {intake.study_id}",
            study_id=intake.study_id,
            description=(
                f"Compiled Study Brief from {msg_count} conversation turns "
                f"covering {len(intake.domains_completed)} domains"
            ),
            properties={
                "domains_covered": intake.domains_completed,
                "message_count": msg_count,
                "sections": list(brief_content.keys()),
            },
            actor_agent_id=_AGENT_NAME,
        )

        # CIP: find the intake session node and link brief → intake
        intake_node = await self._graph_svc.find_node_for_domain_record(
            external_id=intake_id,
            external_type="sponsor_intake",
            organization_id=organization_id,
        )
        if intake_node:
            await self._graph_svc.create_relationship(
                organization_id=organization_id,
                source_node_id=brief_node.id,
                target_node_id=intake_node.id,
                edge_type=GraphEdgeType.GENERATED_FROM,
                study_id=intake.study_id,
                is_ai_generated=True,
                ai_decision_id=decision.id,
                confidence=0.95,
                actor_agent_id=_AGENT_NAME,
            )

        # CIP: complete the compilation decision
        await self._ai_decision_svc.complete_decision(
            decision=decision,
            output={
                "brief_id": str(brief.id),
                "sections_compiled": list(brief_content.keys()),
                "domains_covered": intake.domains_completed,
            },
            reasoning=(
                f"Synthesised {msg_count} conversation turns covering "
                f"{len(intake.domains_completed)}/9 domains into a structured "
                f"Study Brief with {len(brief_content)} sections"
            ),
            confidence=0.95,
            graph_node_id=brief_node.id,
        )

        # Update intake node to reflect compiled status
        if intake_node:
            await self._graph_svc.register_domain_record(
                organization_id=organization_id,
                node_type=GraphNodeType.INTAKE_SESSION,
                external_id=intake_id,
                external_type="sponsor_intake",
                label=f"Intake: {intake.study_id}",
                study_id=intake.study_id,
                properties={
                    "status": "COMPILED",
                    "domains_completed": intake.domains_completed,
                    "brief_id": str(brief.id),
                },
                actor_agent_id=_AGENT_NAME,
            )

        intake.status = IntakeStatus.COMPILED
        await self._db.commit()
        await self._db.refresh(brief)
        return brief

    async def get_session(
        self, intake_id: UUID, organization_id: UUID
    ) -> SponsorIntake:
        """Return the session with all visible messages."""
        return await self._load_session(intake_id, organization_id)

    async def get_brief(self, intake_id: UUID, organization_id: UUID) -> StudyBrief:
        """Return the compiled brief, or 404 if not yet compiled."""
        result = await self._db.execute(
            select(StudyBrief).where(
                StudyBrief.intake_id == intake_id,
                StudyBrief.organization_id == organization_id,
            )
        )
        brief = result.scalar_one_or_none()
        if brief is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "NOT_FOUND",
                    "message": "Study brief not yet compiled.",
                },
            )
        return brief

    async def list_for_study(
        self, study_id: UUID, organization_id: UUID
    ) -> list[SponsorIntake]:
        """List all intake sessions for a study, newest first."""
        result = await self._db.execute(
            select(SponsorIntake)
            .where(
                SponsorIntake.study_id == study_id,
                SponsorIntake.organization_id == organization_id,
            )
            .options(selectinload(SponsorIntake.messages))
            .order_by(SponsorIntake.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_active(
        self, intake_id: UUID, organization_id: UUID
    ) -> SponsorIntake:
        result = await self._db.execute(
            select(SponsorIntake)
            .where(
                SponsorIntake.id == intake_id,
                SponsorIntake.organization_id == organization_id,
            )
            .options(selectinload(SponsorIntake.messages))
        )
        intake = result.scalar_one_or_none()
        if intake is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Intake session not found."},
            )
        if intake.status == IntakeStatus.COMPILED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "ALREADY_COMPILED",
                    "message": "This intake session has already been compiled into a Study Brief.",
                },
            )
        return intake

    async def _load_session(
        self, intake_id: UUID, organization_id: UUID
    ) -> SponsorIntake:
        result = await self._db.execute(
            select(SponsorIntake)
            .where(
                SponsorIntake.id == intake_id,
                SponsorIntake.organization_id == organization_id,
            )
            .options(
                selectinload(SponsorIntake.messages),
                selectinload(SponsorIntake.brief),
            )
        )
        intake = result.scalar_one_or_none()
        if intake is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Intake session not found."},
            )
        return intake

    async def _call_claude_conversation(
        self,
        messages: list[dict],
        *,
        study_name: str = "",
        current_domain: str | None = None,
        domains_completed: list[str] | None = None,
        is_start: bool = False,
    ) -> str:
        if self._client is None:
            parsed = self._fallback_conversation_response(
                study_name=study_name,
                current_domain=current_domain,
                domains_completed=domains_completed or [],
                is_start=is_start,
            )
            return json.dumps(parsed)

        from typing import cast
        from anthropic.types import MessageParam

        completed = domains_completed or []
        remaining = [d for d in _DOMAIN_ORDER if d not in completed]
        state_note = (
            f"\n\nINTAKE STATE (authoritative — do not contradict): "
            f"domains_completed={completed}. "
            f"active_domain={current_domain}. "
            f"remaining_domains={remaining}. "
            f"Never re-ask a domain already in domains_completed."
        )
        response = await self._client.messages.create(
            model=_INTAKE_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT + state_note,
            messages=cast(list[MessageParam], messages),
        )
        block = response.content[0]
        return block.text if isinstance(block, TextBlock) else ""

    @staticmethod
    def _fallback_conversation_response(
        *,
        study_name: str,
        current_domain: str | None,
        domains_completed: list[str],
        is_start: bool,
    ) -> dict:
        """Deterministic intake flow when Anthropic API key is not configured."""
        if is_start:
            return {
                "message": (
                    f"Hello! I'm your TrialGenesis intake specialist. I'll guide you "
                    f'through nine clinical domains for "{study_name}". '
                    f"{_DOMAIN_QUESTIONS['STUDY_OVERVIEW']}"
                ),
                "domain": "STUDY_OVERVIEW",
                "domains_completed": [],
                "ready_to_compile": False,
                "reasoning": (
                    "Opened intake session with study overview "
                    "(deterministic fallback — no API key configured)."
                ),
            }

        completed = list(domains_completed)
        if current_domain and current_domain not in completed:
            completed.append(current_domain)

        remaining = [d for d in _DOMAIN_ORDER if d not in completed]
        if not remaining:
            return {
                "message": (
                    "Thank you — all nine intake domains are covered. "
                    "You can now compile the Study Brief."
                ),
                "domain": "SITES",
                "domains_completed": completed,
                "ready_to_compile": True,
                "reasoning": (
                    "All domains complete (deterministic fallback — no API key configured)."
                ),
            }

        next_domain = remaining[0]
        return {
            "message": (
                f"Thank you for that information. {_DOMAIN_QUESTIONS[next_domain]}"
            ),
            "domain": next_domain,
            "domains_completed": completed,
            "ready_to_compile": False,
            "reasoning": (
                f"Recorded {current_domain} and advanced to {next_domain} "
                "(deterministic fallback — no API key configured)."
            ),
        }

    @staticmethod
    def _extract_domain_answers(messages: list[IntakeMessage]) -> dict[str, str]:
        """Map each intake domain to the user's answer that followed it."""
        answers: dict[str, str] = {}
        pending_domain: str | None = None
        for msg in messages:
            if msg.role == "assistant" and msg.domain:
                pending_domain = msg.domain
            elif msg.role == "user" and pending_domain:
                answers[pending_domain] = msg.content.strip()
                pending_domain = None
        return answers

    @staticmethod
    def _fallback_brief_content(study, domain_answers: dict[str, str]) -> dict:
        """Build a structured Study Brief from domain answers without AI."""
        overview = domain_answers.get("STUDY_OVERVIEW", "")
        return {
            "study_overview": {
                "title": study.name,
                "therapeutic_area": overview[:120] or "TBD",
                "indication": overview[120:240] or "TBD",
                "phase": study.phase.value if study.phase else "TBD",
                "sponsor": "TBD",
                "compound_code": study.protocol_number,
            },
            "study_design": {
                "design_type": domain_answers.get("STUDY_DESIGN", "TBD"),
                "randomization": "TBD",
                "blinding": "TBD",
                "comparator": None,
                "treatment_duration": "TBD",
                "number_of_periods": 1,
            },
            "population": {
                "description": domain_answers.get("POPULATION", "TBD"),
                "inclusion_criteria": [],
                "exclusion_criteria": [],
                "age_range": {"min": 18, "max": None},
                "estimated_sample_size": None,
            },
            "endpoints": {
                "primary": [
                    {
                        "name": domain_answers.get("ENDPOINTS", "TBD"),
                        "timepoint": "TBD",
                        "instrument": None,
                    }
                ],
                "secondary": [],
                "safety": [],
            },
            "drug_treatment": {
                "inn_name": domain_answers.get("DRUG_TREATMENT", "TBD"),
                "doses": [],
                "route": "TBD",
                "formulation": None,
                "regimen": "TBD",
            },
            "safety": {
                "key_concerns": [domain_answers.get("SAFETY", "TBD")],
                "monitoring_approach": "TBD",
                "stopping_rules": [],
                "sae_definitions": None,
                "rems_required": False,
            },
            "regulatory": {
                "regions": [],
                "ind_cta_status": domain_answers.get("REGULATORY", "TBD"),
                "submission_type": None,
                "gcp_standard": "ICH E6(R2)",
                "special_designations": [],
            },
            "statistical": {
                "framework": "FREQUENTIST",
                "primary_analysis_method": domain_answers.get("STATISTICAL", "TBD"),
                "alpha_level": 0.05,
                "multiple_testing_approach": None,
                "key_subgroups": [],
            },
            "sites": {
                "planned_sites": None,
                "countries": [],
                "estimated_enrollment_rate_per_month": None,
                "site_selection_criteria": [
                    domain_answers.get("SITES", "TBD"),
                ],
            },
        }

    @staticmethod
    def _current_domain(messages: list[IntakeMessage]) -> str | None:
        """Return the domain from the most recent assistant turn."""
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.domain:
                return msg.domain
        return None

    @classmethod
    def _merge_domains_completed(
        cls,
        existing: list[str],
        incoming: list[str] | None,
    ) -> list[str]:
        """Union domain completion lists while preserving canonical order."""
        merged: list[str] = []
        seen: set[str] = set()
        for domain in _DOMAIN_ORDER:
            if domain in existing or (incoming and domain in incoming):
                if domain not in seen:
                    merged.append(domain)
                    seen.add(domain)
        return merged

    @classmethod
    def _next_domain(cls, domains_completed: list[str]) -> str | None:
        for domain in _DOMAIN_ORDER:
            if domain not in domains_completed:
                return domain
        return None

    @classmethod
    def _normalize_intake_progress(
        cls,
        *,
        domains_completed: list[str],
        parsed: dict,
        current_domain: str | None = None,
        user_answered: bool = False,
    ) -> dict:
        """Enforce monotonic domain progression and prevent repeated questions."""
        merged = cls._merge_domains_completed(
            domains_completed,
            parsed.get("domains_completed"),
        )
        if user_answered and current_domain and current_domain in _DOMAIN_ORDER:
            if current_domain not in merged:
                merged = cls._merge_domains_completed(merged, [current_domain])

        next_domain = cls._next_domain(merged)
        ready = bool(parsed.get("ready_to_compile")) and next_domain is None
        domain = parsed.get("domain") or current_domain or next_domain

        if domain in merged and not ready:
            domain = next_domain

        if ready:
            domain = "SITES"
            message = parsed.get(
                "message",
                "Thank you — all nine intake domains are covered. "
                "You can now compile the Study Brief.",
            )
        elif domain and domain in _DOMAIN_ORDER:
            if domain != parsed.get("domain"):
                message = f"Thank you for that information. {_DOMAIN_QUESTIONS[domain]}"
            else:
                message = parsed.get("message", _DOMAIN_QUESTIONS[domain])
        else:
            domain = next_domain or "STUDY_OVERVIEW"
            message = parsed.get("message", _DOMAIN_QUESTIONS[domain])

        return {
            "message": message,
            "domain": domain,
            "domains_completed": merged,
            "ready_to_compile": ready,
            "reasoning": parsed.get("reasoning"),
        }

    def _parse_ai_response(self, text: str) -> dict:
        """Parse the JSON envelope from Claude's intake response."""
        parsed = self._extract_json(text)
        return {
            "message": parsed.get("message", text),
            "domain": parsed.get("domain"),
            "domains_completed": parsed.get("domains_completed", []),
            "ready_to_compile": bool(parsed.get("ready_to_compile", False)),
            "reasoning": parsed.get("reasoning"),
        }

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from a Claude response, handling markdown fences."""
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return {
            "message": text,
            "domain": None,
            "domains_completed": [],
            "ready_to_compile": False,
        }
