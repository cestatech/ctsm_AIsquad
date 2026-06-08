"""EDC/eCRF specification generator — structured JSON from Study Brief and protocol."""

from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select

from app.models.artifact import Artifact, ArtifactType
from app.models.generation import GenerationJob
from app.models.graph import GraphEdgeType, GraphNodeType
from app.models.intelligence import AIDecision
from app.models.study import Study
from app.services.generators.base_generator import BaseGenerator
from app.services.generators.edc_content_builder import build_edc_content


class EDCGenerator(BaseGenerator):
    ARTIFACT_TYPE = ArtifactType.EDC_CRF
    AGENT_NAME = "edc-generator"

    def _artifact_name(self, study_name: str) -> str:
        return f"{study_name} — EDC/eCRF Specification v1.0"

    async def _build_content(
        self, job: GenerationJob, study: Study, model_id: str
    ) -> dict:
        ctx = job.input_context or {}
        brief_content = ctx.get("brief_content")
        protocol_content = None
        source_ids: list[str] = []

        if ctx.get("brief_id"):
            source_ids.append(str(ctx["brief_id"]))

        protocol_id = ctx.get("protocol_artifact_id")
        if protocol_id:
            source_ids.append(str(protocol_id))
            protocol_content = await self._load_artifact_content(
                UUID(str(protocol_id)), job.organization_id
            )
        elif not brief_content:
            protocol_artifact = await self._find_latest_artifact(
                job.study_id, job.organization_id, ArtifactType.PROTOCOL
            )
            if protocol_artifact:
                source_ids.append(str(protocol_artifact.id))
                protocol_content = await self._artifact_content(protocol_artifact)

        sap_id = ctx.get("sap_artifact_id")
        if sap_id:
            source_ids.append(str(sap_id))

        return build_edc_content(
            study_id=job.study_id,
            study_name=study.name,
            protocol_number=study.protocol_number,
            brief_content=brief_content if isinstance(brief_content, dict) else None,
            protocol_content=protocol_content,
            source_artifact_ids=source_ids,
        )

    async def _register_additional_graph(
        self,
        job: GenerationJob,
        study: Study,
        artifact: Artifact,
        actor: object,
        decision: object,
        art_node_id: UUID,
        content: dict,
    ) -> None:
        """Register EDC lineage nodes: visits, forms, fields, edit checks, assessments."""
        assert isinstance(decision, AIDecision)

        study_node, _ = await self._graph_svc.register_domain_record(
            organization_id=job.organization_id,
            node_type=GraphNodeType.STUDY,
            external_id=study.id,
            external_type="study",
            label=study.name,
            study_id=study.id,
            actor_agent_id=self.AGENT_NAME,
        )

        soa_node, _ = await self._graph_svc.register_domain_record(
            organization_id=job.organization_id,
            node_type=GraphNodeType.ASSESSMENT,
            external_id=artifact.id,
            external_type="schedule_of_assessments",
            label=f"SOA — {study.name}",
            study_id=job.study_id,
            properties={"artifact_id": str(artifact.id)},
            actor_agent_id=self.AGENT_NAME,
        )
        await self._graph_svc.create_relationship(
            organization_id=job.organization_id,
            source_node_id=art_node_id,
            target_node_id=soa_node.id,
            edge_type=GraphEdgeType.GENERATED_FROM,
            study_id=job.study_id,
            is_ai_generated=True,
            ai_decision_id=decision.id,
            actor_agent_id=self.AGENT_NAME,
        )

        def _stable_id(key: str) -> UUID:
            return uuid.uuid5(artifact.id, key)

        visit_nodes: dict[str, UUID] = {}
        for visit in content.get("visit_schedule") or []:
            vid = visit["visit_id"]
            v_node, _ = await self._graph_svc.register_domain_record(
                organization_id=job.organization_id,
                node_type=GraphNodeType.VISIT,
                external_id=_stable_id(f"visit:{vid}"),
                external_type="visit",
                label=visit["label"],
                study_id=job.study_id,
                properties={"visit_id": vid, "day": visit.get("day")},
                actor_agent_id=self.AGENT_NAME,
            )
            visit_nodes[vid] = v_node.id
            await self._graph_svc.create_relationship(
                organization_id=job.organization_id,
                source_node_id=soa_node.id,
                target_node_id=v_node.id,
                edge_type=GraphEdgeType.PART_OF,
                study_id=job.study_id,
                actor_agent_id=self.AGENT_NAME,
            )

        form_nodes: dict[str, UUID] = {}
        for form in content.get("forms") or []:
            fid = form["form_id"]
            f_node, _ = await self._graph_svc.register_domain_record(
                organization_id=job.organization_id,
                node_type=GraphNodeType.ECR_FORM,
                external_id=_stable_id(f"form:{fid}"),
                external_type="ecr_form",
                label=form["form_name"],
                study_id=job.study_id,
                properties={"form_id": fid},
                actor_agent_id=self.AGENT_NAME,
            )
            form_nodes[fid] = f_node.id
            await self._graph_svc.create_relationship(
                organization_id=job.organization_id,
                source_node_id=f_node.id,
                target_node_id=art_node_id,
                edge_type=GraphEdgeType.PART_OF,
                study_id=job.study_id,
                actor_agent_id=self.AGENT_NAME,
            )

        for field in content.get("fields") or []:
            field_id = field["field_id"]
            form_id = field["form_id"]
            fl_node, _ = await self._graph_svc.register_domain_record(
                organization_id=job.organization_id,
                node_type=GraphNodeType.ECR_FIELD,
                external_id=_stable_id(f"field:{field_id}"),
                external_type="ecr_field",
                label=field["label"],
                study_id=job.study_id,
                properties={
                    "field_id": field_id,
                    "sdtm_mapping": field.get("sdtm_mapping"),
                    "context_graph_hint": field.get("context_graph_hint"),
                },
                actor_agent_id=self.AGENT_NAME,
            )
            if form_id in form_nodes:
                await self._graph_svc.create_relationship(
                    organization_id=job.organization_id,
                    source_node_id=fl_node.id,
                    target_node_id=form_nodes[form_id],
                    edge_type=GraphEdgeType.PART_OF,
                    study_id=job.study_id,
                    actor_agent_id=self.AGENT_NAME,
                )
            for vid in field.get("visit_ids") or []:
                if vid in visit_nodes:
                    await self._graph_svc.create_relationship(
                        organization_id=job.organization_id,
                        source_node_id=visit_nodes[vid],
                        target_node_id=fl_node.id,
                        edge_type=GraphEdgeType.ENDPOINT_TO_ECR,
                        study_id=job.study_id,
                        is_ai_generated=True,
                        ai_decision_id=decision.id,
                        actor_agent_id=self.AGENT_NAME,
                    )
            sdtm = field.get("sdtm_mapping")
            if sdtm:
                sdtm_node, _ = await self._graph_svc.register_domain_record(
                    organization_id=job.organization_id,
                    node_type=GraphNodeType.SDTM_VARIABLE,
                    external_id=_stable_id(f"sdtm:{sdtm}"),
                    external_type="sdtm_variable",
                    label=sdtm,
                    study_id=job.study_id,
                    actor_agent_id=self.AGENT_NAME,
                )
                await self._graph_svc.link_ecr_to_sdtm(
                    org_id=job.organization_id,
                    study_id=job.study_id,
                    ecr_node_id=fl_node.id,
                    sdtm_node_id=sdtm_node.id,
                    is_ai_generated=True,
                    ai_decision_id=decision.id,
                    actor_agent_id=self.AGENT_NAME,
                )

        for check in content.get("edit_checks") or []:
            ec_node, _ = await self._graph_svc.register_domain_record(
                organization_id=job.organization_id,
                node_type=GraphNodeType.EDIT_CHECK,
                external_id=_stable_id(f"check:{check['check_id']}"),
                external_type="edit_check",
                label=check["rule"],
                study_id=job.study_id,
                properties={"field_id": check.get("field_id")},
                actor_agent_id=self.AGENT_NAME,
            )
            await self._graph_svc.create_relationship(
                organization_id=job.organization_id,
                source_node_id=ec_node.id,
                target_node_id=art_node_id,
                edge_type=GraphEdgeType.VALIDATES,
                study_id=job.study_id,
                actor_agent_id=self.AGENT_NAME,
            )

        for screen in content.get("mock_screens") or []:
            screen_node, _ = await self._graph_svc.register_domain_record(
                organization_id=job.organization_id,
                node_type=GraphNodeType.ECR_FORM,
                external_id=_stable_id(f"screen:{screen['screen_id']}"),
                external_type="mock_screen",
                label=f"Mock Screen — {screen['form_name']}",
                study_id=job.study_id,
                properties={"screen_id": screen["screen_id"], "is_mock_screen": True},
                actor_agent_id=self.AGENT_NAME,
            )
            form_nid = form_nodes.get(screen["form_id"])
            if form_nid:
                await self._graph_svc.create_relationship(
                    organization_id=job.organization_id,
                    source_node_id=form_nid,
                    target_node_id=screen_node.id,
                    edge_type=GraphEdgeType.USED_IN,
                    study_id=job.study_id,
                    actor_agent_id=self.AGENT_NAME,
                )

        ctx = job.input_context or {}
        if ctx.get("protocol_artifact_id"):
            try:
                proto_node, _ = await self._graph_svc.register_domain_record(
                    organization_id=job.organization_id,
                    node_type=GraphNodeType.PROTOCOL,
                    external_id=UUID(str(ctx["protocol_artifact_id"])),
                    external_type="artifact",
                    label="Protocol",
                    study_id=job.study_id,
                    actor_agent_id=self.AGENT_NAME,
                )
                await self._graph_svc.create_relationship(
                    organization_id=job.organization_id,
                    source_node_id=proto_node.id,
                    target_node_id=soa_node.id,
                    edge_type=GraphEdgeType.GENERATED_FROM,
                    study_id=job.study_id,
                    is_ai_generated=True,
                    ai_decision_id=decision.id,
                    actor_agent_id=self.AGENT_NAME,
                )
            except (ValueError, TypeError):
                pass

        await self._graph_svc.emit_event(
            organization_id=job.organization_id,
            study_id=job.study_id,
            event_type="EDC_SPECIFICATION_GENERATED",
            actor_agent_id=self.AGENT_NAME,
            ai_decision_id=decision.id,
            node_id=art_node_id,
            payload={
                "forms": len(content.get("forms") or []),
                "fields": len(content.get("fields") or []),
                "visits": len(content.get("visit_schedule") or []),
                "mock_screens": len(content.get("mock_screens") or []),
            },
        )

    def _graph_event_type(self) -> str | None:
        """Detailed EDC event is emitted in _register_additional_graph."""
        return None

    async def _load_artifact_content(
        self, artifact_id: UUID, organization_id: UUID
    ) -> dict | None:
        result = await self._db.execute(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.organization_id == organization_id,
            )
        )
        artifact = result.scalar_one_or_none()
        if artifact is None:
            return None
        return await self._artifact_content(artifact)

    async def _find_latest_artifact(
        self, study_id: UUID, organization_id: UUID, artifact_type: ArtifactType
    ) -> Artifact | None:
        result = await self._db.execute(
            select(Artifact)
            .where(
                Artifact.study_id == study_id,
                Artifact.organization_id == organization_id,
                Artifact.artifact_type == artifact_type,
            )
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _artifact_content(self, artifact: Artifact) -> dict | None:
        if artifact.current_version_id is None:
            return None
        from app.models.artifact import ArtifactVersion

        result = await self._db.execute(
            select(ArtifactVersion).where(
                ArtifactVersion.id == artifact.current_version_id
            )
        )
        version = result.scalar_one_or_none()
        return version.content if version else None
