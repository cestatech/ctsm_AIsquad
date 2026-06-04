"""Study service — CRUD, membership management, and CIP integration.

Every mutation emits an AuditLog record and a Context Graph event.
Study creation also registers the study as a STUDY node in the Context Graph.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, Role, check_permission
from app.models.audit import AuditAction
from app.models.graph import GraphNodeType
from app.models.study import Study, StudyMember, StudyStatus
from app.models.user import User
from app.repositories.study_repository import StudyRepository
from app.schemas.study import StudyCreate, StudyUpdate
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService


class StudyService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = StudyRepository(db)
        self._audit = AuditService(db)
        self._graph = ContextGraphService(db)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, study_id: UUID, organization_id: UUID) -> Study:
        return await self._repo.get(study_id, organization_id)

    async def list(
        self,
        organization_id: UUID,
        status_filter: StudyStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Study], int]:
        offset = (page - 1) * page_size
        return await self._repo.list(
            organization_id=organization_id,
            status_filter=status_filter,
            limit=page_size,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        body: StudyCreate,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Study:
        check_permission(actor, Permission.STUDY_CREATE)

        existing = await self._repo.get_by_protocol_number(
            body.protocol_number, actor.organization_id
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "PROTOCOL_NUMBER_EXISTS",
                    "message": f"Protocol number '{body.protocol_number}' already exists.",
                },
            )

        study = Study(
            organization_id=actor.organization_id,
            protocol_number=body.protocol_number,
            name=body.name,
            short_name=body.short_name,
            description=body.description,
            indication=body.indication,
            therapeutic_area=body.therapeutic_area,
            phase=body.phase,
            status=StudyStatus.DRAFT,
            sponsor=body.sponsor,
            regulatory_region=body.regulatory_region,
            start_date=body.start_date,
            end_date=body.end_date,
            created_by_id=actor.id,
        )
        study = await self._repo.create(study)

        # Auto-add the creator as Admin member
        member = StudyMember(
            study_id=study.id,
            user_id=actor.id,
            organization_id=actor.organization_id,
            role=Role.ADMIN,
        )
        await self._repo.add_member(member)

        await self._audit.log(
            action=AuditAction.STUDY_CREATED,
            resource_type="study",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=study.id,
            after_state=study.to_audit_dict(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Register as STUDY node in the Context Graph
        node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.STUDY,
            external_id=study.id,
            external_type="study",
            label=f"{body.protocol_number}: {body.name}",
            study_id=study.id,
            description=body.description,
            properties={
                "phase": body.phase.value if body.phase else None,
                "indication": body.indication,
                "therapeutic_area": body.therapeutic_area,
                "sponsor": body.sponsor,
                "regulatory_region": body.regulatory_region,
            },
            actor=actor,
        )

        await self._graph.emit_event(
            organization_id=actor.organization_id,
            event_type="STUDY_CREATED",
            study_id=study.id,
            node_id=node.id,
            actor_user_id=actor.id,
            payload={
                "study_id": str(study.id),
                "protocol_number": body.protocol_number,
                "name": body.name,
                "phase": body.phase.value if body.phase else None,
            },
        )

        return study

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self,
        study_id: UUID,
        body: StudyUpdate,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Study:
        study = await self._repo.get(study_id, actor.organization_id)
        study_role = await self._repo.get_member_role(
            study_id, actor.id, actor.organization_id
        )
        check_permission(actor, Permission.ARTIFACT_EDIT, study_role)

        if not study.is_editable():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "STUDY_NOT_EDITABLE",
                    "message": f"Study with status {study.status} cannot be edited.",
                },
            )

        before = study.to_audit_dict()

        update_data = body.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(study, field, value)

        study = await self._repo.update(study)

        await self._audit.log(
            action=AuditAction.STUDY_UPDATED,
            resource_type="study",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=study.id,
            before_state=before,
            after_state=study.to_audit_dict(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._graph.emit_event(
            organization_id=actor.organization_id,
            event_type="STUDY_UPDATED",
            study_id=study.id,
            actor_user_id=actor.id,
            payload={"study_id": str(study.id), "changes": list(update_data.keys())},
        )

        return study

    # ------------------------------------------------------------------
    # Archive
    # ------------------------------------------------------------------

    async def archive(
        self,
        study_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Study:
        check_permission(actor, Permission.STUDY_ARCHIVE)
        study = await self._repo.get(study_id, actor.organization_id)

        if study.status == StudyStatus.ARCHIVED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "ALREADY_ARCHIVED",
                    "message": "Study is already archived.",
                },
            )

        before = study.to_audit_dict()
        study.status = StudyStatus.ARCHIVED
        study = await self._repo.update(study)

        await self._audit.log(
            action=AuditAction.STUDY_ARCHIVED,
            resource_type="study",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=study.id,
            before_state=before,
            after_state=study.to_audit_dict(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._graph.emit_event(
            organization_id=actor.organization_id,
            event_type="STUDY_ARCHIVED",
            study_id=study.id,
            actor_user_id=actor.id,
            payload={"study_id": str(study.id)},
        )

        return study

    # ------------------------------------------------------------------
    # Member management
    # ------------------------------------------------------------------

    async def list_members(
        self, study_id: UUID, organization_id: UUID
    ) -> list[StudyMember]:
        await self._repo.get(study_id, organization_id)
        return await self._repo.list_members(study_id, organization_id)

    async def add_member(
        self,
        study_id: UUID,
        user_id: UUID,
        role: Role,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> StudyMember:
        check_permission(actor, Permission.STUDY_MANAGE_MEMBERS)
        await self._repo.get(study_id, actor.organization_id)

        existing = await self._repo.get_member(study_id, user_id, actor.organization_id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "ALREADY_MEMBER",
                    "message": "User is already a member of this study.",
                },
            )

        member = StudyMember(
            study_id=study_id,
            user_id=user_id,
            organization_id=actor.organization_id,
            role=role,
            invited_by_id=actor.id,
        )
        member = await self._repo.add_member(member)

        await self._audit.log(
            action=AuditAction.STUDY_MEMBER_ADDED,
            resource_type="study_member",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=study_id,
            after_state={"user_id": str(user_id), "role": role},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._graph.emit_event(
            organization_id=actor.organization_id,
            event_type="STUDY_MEMBER_ADDED",
            study_id=study_id,
            actor_user_id=actor.id,
            payload={"study_id": str(study_id), "user_id": str(user_id), "role": role},
        )

        return member

    async def remove_member(
        self,
        study_id: UUID,
        user_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        check_permission(actor, Permission.STUDY_MANAGE_MEMBERS)

        # Prevent removing yourself as the last Admin
        if user_id == actor.id:
            members = await self._repo.list_members(study_id, actor.organization_id)
            admins = [m for m in members if m.role == Role.ADMIN]
            if len(admins) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "LAST_ADMIN",
                        "message": "Cannot remove the last Admin from a study.",
                    },
                )

        member = await self._repo.get_member(study_id, user_id, actor.organization_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Member not found."},
            )

        await self._repo.remove_member(member)

        await self._audit.log(
            action=AuditAction.STUDY_MEMBER_REMOVED,
            resource_type="study_member",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=study_id,
            before_state={"user_id": str(user_id), "role": member.role},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._graph.emit_event(
            organization_id=actor.organization_id,
            event_type="STUDY_MEMBER_REMOVED",
            study_id=study_id,
            actor_user_id=actor.id,
            payload={"study_id": str(study_id), "user_id": str(user_id)},
        )

    async def update_member_role(
        self,
        study_id: UUID,
        user_id: UUID,
        new_role: Role,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> StudyMember:
        check_permission(actor, Permission.STUDY_MANAGE_MEMBERS)

        member = await self._repo.get_member(study_id, user_id, actor.organization_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Member not found."},
            )

        # Prevent demoting the last Admin
        if member.role == Role.ADMIN and new_role != Role.ADMIN:
            members = await self._repo.list_members(study_id, actor.organization_id)
            admins = [m for m in members if m.role == Role.ADMIN]
            if len(admins) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "LAST_ADMIN",
                        "message": "Cannot demote the last Admin of a study.",
                    },
                )

        old_role = member.role
        member.role = new_role
        await self._db.flush()

        await self._audit.log(
            action=AuditAction.STUDY_MEMBER_ROLE_CHANGED,
            resource_type="study_member",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=study_id,
            before_state={"user_id": str(user_id), "role": old_role},
            after_state={"user_id": str(user_id), "role": new_role},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._graph.emit_event(
            organization_id=actor.organization_id,
            event_type="STUDY_MEMBER_ROLE_CHANGED",
            study_id=study_id,
            actor_user_id=actor.id,
            payload={
                "study_id": str(study_id),
                "user_id": str(user_id),
                "old_role": old_role,
                "new_role": new_role,
            },
        )

        return member
