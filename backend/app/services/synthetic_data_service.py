"""
Synthetic data generation service — MVP reproducible patient-level datasets.

Requires a SAP artifact. Also uses Protocol and EDC_CRF artifacts when available.
Output is always labeled SYNTHETIC.
"""

from __future__ import annotations

import csv
import io
import random
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import Permission, check_permission
from app.models.artifact import Artifact, ArtifactType, ArtifactVersion
from app.models.audit import AuditAction
from app.models.graph import GraphEdgeType, GraphNodeType
from app.models.data_source import DataSourceType
from app.models.intelligence import SimulationAssumption, SyntheticDataRun
from app.services.data_cut_service import DataCutContext
from app.models.study import Study
from app.models.user import User
from app.repositories.intelligence_repository import SyntheticDataRepository
from app.repositories.study_repository import StudyRepository
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService
from app.services.intelligence_service import AIDecisionService, DataLineageService


class SyntheticDataService:
    """Create and execute synthetic data generation runs."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = SyntheticDataRepository(db)
        self._study_repo = StudyRepository(db)
        self._artifact_svc = ArtifactService(db)
        self._audit = AuditService(db)
        self._ai_decision = AIDecisionService(db)
        self._graph = ContextGraphService(db)
        self._lineage = DataLineageService(db)

    async def create_run(
        self,
        study_id: UUID,
        target_n: int,
        random_seed: int,
        actor: User,
        run_name: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SyntheticDataRun:
        """Start a synthetic data generation run."""
        check_permission(actor, Permission.AI_GENERATION_TRIGGER)

        study = await self._study_repo.get(study_id, actor.organization_id)

        sap = await self._latest_artifact(
            study_id, actor.organization_id, ArtifactType.SAP
        )
        if sap is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "SAP_REQUIRED",
                    "message": (
                        "A Statistical Analysis Plan (SAP) artifact is required "
                        "before generating synthetic data."
                    ),
                },
            )

        decision = await self._ai_decision.begin_decision(
            organization_id=actor.organization_id,
            agent_name="synthetic-data-generator",
            decision_type="SYNTHETIC_DATA_GENERATION",
            study_id=study_id,
            input_context={
                "target_n": target_n,
                "random_seed": random_seed,
            },
        )

        existing_runs, _ = await self._repo.list_runs_for_study(
            study_id=study_id,
            organization_id=actor.organization_id,
            limit=1000,
            offset=0,
        )
        version_number = len(existing_runs) + 1
        data_cut_label = f"Synthetic Data Version {version_number}"

        run = SyntheticDataRun(
            organization_id=actor.organization_id,
            study_id=study_id,
            run_name=run_name or f"Synthetic Run — {data_cut_label}",
            description="MVP synthetic patient-level eCRF export (labeled SYNTHETIC)",
            target_n=target_n,
            random_seed=random_seed,
            configuration={
                "label": "SYNTHETIC",
                "format": "CSV",
                "reproducible": True,
                "data_cut_label": data_cut_label,
            },
            status="RUNNING",
            started_at=datetime.now(UTC),
            created_by_id=actor.id,
            data_source_type=DataSourceType.SYNTHETIC,
            data_cut_label=data_cut_label,
            data_cut_date=datetime.now(UTC).date(),
            is_synthetic=True,
        )
        run = await self._repo.create_run(run)
        run.data_cut_id = run.id
        await self._db.flush()

        try:
            protocol = await self._latest_artifact(
                study_id, actor.organization_id, ArtifactType.PROTOCOL
            )
            edc = await self._latest_artifact(
                study_id, actor.organization_id, ArtifactType.EDC_CRF
            )

            protocol_content = await self._artifact_content(protocol)
            sap_content = await self._artifact_content(sap)
            edc_content = await self._artifact_content(edc)

            assumptions = self._build_assumptions(
                run=run,
                study=study,
                protocol_content=protocol_content,
                sap_content=sap_content,
                edc_content=edc_content,
                target_n=target_n,
                random_seed=random_seed,
            )
            for assumption in assumptions:
                assumption.run_id = run.id
                assumption.organization_id = actor.organization_id
                await self._repo.create_assumption(assumption)

            dataset = self._generate_dataset(
                study=study,
                target_n=target_n,
                random_seed=random_seed,
                protocol_content=protocol_content,
                sap_content=sap_content,
                edc_content=edc_content,
            )

            source_ids = [str(a.id) for a in (protocol, sap, edc) if a]
            data_cut = DataCutContext.for_synthetic_run(
                study_id=study_id,
                created_by=actor.id,
                run_id=run.id,
                version_number=version_number,
            )
            dataset = data_cut.embed_in_content(dataset)
            output_artifact = await self._artifact_svc.create_artifact(
                organization_id=actor.organization_id,
                study_id=study_id,
                user=actor,
                artifact_type=ArtifactType.OTHER,
                name=f"{study.name} — Synthetic Raw Clinical Data — {data_cut_label}",
                description=(
                    f"SYNTHETIC patient-level CSV — {data_cut_label}. "
                    "NOT real patient data."
                ),
                content=dataset,
                change_summary=f"Synthetic data run {run.id} (seed={random_seed}, n={target_n})",
                metadata={"data_cut": data_cut.to_dict()},
            )

            run.status = "COMPLETED"
            run.records_generated = target_n
            run.output_artifact_id = output_artifact.id
            run.completed_at = datetime.now(UTC)
            run.configuration = {
                **run.configuration,
                "source_artifact_ids": source_ids,
                "domains_generated": list(dataset.get("datasets", {}).keys()),
            }
            await self._db.flush()

            await self._ai_decision.complete_decision(
                decision=decision,
                output={
                    "run_id": str(run.id),
                    "records_generated": target_n,
                    "output_artifact_id": str(output_artifact.id),
                },
                reasoning=(
                    f"Generated {target_n} synthetic subjects with seed {random_seed} "
                    f"using protocol={'yes' if protocol else 'no'}, "
                    f"SAP={'yes' if sap else 'no'}, "
                    f"EDC={'yes' if edc else 'no'}."
                ),
                confidence=0.85,
                output_artifact_ids=[output_artifact.id],
            )

            await self._register_synthetic_graph(
                run=run,
                study=study,
                output_artifact=output_artifact,
                decision_id=decision.id,
                actor=actor,
                protocol=protocol,
                sap=sap,
                edc=edc,
                assumptions=assumptions,
                target_n=target_n,
                random_seed=random_seed,
            )

            if edc:
                await self._lineage.record_artifact_lineage(
                    organization_id=actor.organization_id,
                    source_artifact_id=edc.id,
                    target_artifact_id=output_artifact.id,
                    relationship_type="SYNTHETIC_DERIVED_FROM",
                    study_id=study_id,
                    derivation_notes="Synthetic eCRF export generated from EDC specification",
                    is_ai_generated=True,
                    ai_decision_id=decision.id,
                    created_by=actor,
                )

            await self._audit.log(
                action=AuditAction.AI_GENERATION_COMPLETED,
                resource_type="synthetic_data_run",
                organization_id=actor.organization_id,
                actor_user_id=actor.id,
                resource_id=run.id,
                after_state={
                    "study_id": str(study_id),
                    "target_n": target_n,
                    "random_seed": random_seed,
                    "output_artifact_id": str(output_artifact.id),
                    "label": "SYNTHETIC",
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

        except Exception as exc:
            run.status = "FAILED"
            run.error_message = str(exc)[:2000]
            run.completed_at = datetime.now(UTC)
            await self._db.flush()
            await self._audit.log(
                action=AuditAction.AI_GENERATION_FAILED,
                resource_type="synthetic_data_run",
                organization_id=actor.organization_id,
                actor_user_id=actor.id,
                resource_id=run.id,
                after_state={"error": run.error_message},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise

        result = await self._db.execute(
            select(SyntheticDataRun)
            .where(SyntheticDataRun.id == run.id)
            .options(selectinload(SyntheticDataRun.assumptions))
        )
        return result.scalar_one()

    async def _register_synthetic_graph(
        self,
        run: SyntheticDataRun,
        study: Study,
        output_artifact: Artifact,
        decision_id: UUID,
        actor: User,
        protocol: Artifact | None,
        sap: Artifact | None,
        edc: Artifact | None,
        assumptions: list[SimulationAssumption],
        target_n: int,
        random_seed: int,
    ) -> None:
        """Register synthetic run, assumptions, and lineage in the context graph."""
        org_id = actor.organization_id
        study_id = study.id
        agent = "synthetic-data-generator"

        run_node, _ = await self._graph.register_domain_record(
            organization_id=org_id,
            node_type=GraphNodeType.SYNTHETIC_DATA_RUN,
            external_id=run.id,
            external_type="synthetic_data_run",
            label=run.run_name,
            study_id=study_id,
            description=run.description,
            properties={
                "target_n": target_n,
                "random_seed": random_seed,
                "label": "SYNTHETIC",
                "status": run.status,
            },
            actor_agent_id=agent,
        )

        study_node, _ = await self._graph.register_domain_record(
            organization_id=org_id,
            node_type=GraphNodeType.STUDY,
            external_id=study.id,
            external_type="study",
            label=study.name,
            study_id=study_id,
            actor_agent_id=agent,
        )
        await self._graph.create_relationship(
            organization_id=org_id,
            source_node_id=run_node.id,
            target_node_id=study_node.id,
            edge_type=GraphEdgeType.PART_OF,
            study_id=study_id,
            actor_agent_id=agent,
        )

        output_node, _ = await self._graph.register_domain_record(
            organization_id=org_id,
            node_type=GraphNodeType.ARTIFACT,
            external_id=output_artifact.id,
            external_type="artifact",
            label=output_artifact.name,
            study_id=study_id,
            properties={
                "artifact_type": output_artifact.artifact_type.value,
                "label": "SYNTHETIC",
            },
            actor_agent_id=agent,
        )
        await self._graph.create_relationship(
            organization_id=org_id,
            source_node_id=output_node.id,
            target_node_id=run_node.id,
            edge_type=GraphEdgeType.GENERATED_FROM,
            study_id=study_id,
            is_ai_generated=True,
            ai_decision_id=decision_id,
            actor_agent_id=agent,
        )

        decision_node, _ = await self._graph.register_domain_record(
            organization_id=org_id,
            node_type=GraphNodeType.AI_DECISION,
            external_id=decision_id,
            external_type="ai_decision",
            label=f"{agent} decision",
            study_id=study_id,
            actor_agent_id=agent,
        )
        await self._graph.create_relationship(
            organization_id=org_id,
            source_node_id=run_node.id,
            target_node_id=decision_node.id,
            edge_type=GraphEdgeType.CREATED_BY,
            study_id=study_id,
            is_ai_generated=True,
            ai_decision_id=decision_id,
            actor_agent_id=agent,
        )

        for source in (protocol, sap, edc):
            if source is None:
                continue
            source_node, _ = await self._graph.register_domain_record(
                organization_id=org_id,
                node_type=GraphNodeType.ARTIFACT,
                external_id=source.id,
                external_type="artifact",
                label=source.name,
                study_id=study_id,
                properties={"artifact_type": source.artifact_type.value},
                actor_agent_id=agent,
            )
            await self._graph.create_relationship(
                organization_id=org_id,
                source_node_id=run_node.id,
                target_node_id=source_node.id,
                edge_type=GraphEdgeType.USED_IN,
                study_id=study_id,
                is_ai_generated=True,
                ai_decision_id=decision_id,
                actor_agent_id=agent,
            )

        for assumption in assumptions:
            assumption_node, _ = await self._graph.register_domain_record(
                organization_id=org_id,
                node_type=GraphNodeType.SIMULATION_ASSUMPTION,
                external_id=assumption.id,
                external_type="simulation_assumption",
                label=assumption.description[:120],
                study_id=study_id,
                properties={
                    "assumption_type": assumption.assumption_type,
                    "domain": assumption.domain,
                },
                actor_agent_id=agent,
            )
            await self._graph.create_relationship(
                organization_id=org_id,
                source_node_id=assumption_node.id,
                target_node_id=run_node.id,
                edge_type=GraphEdgeType.PART_OF,
                study_id=study_id,
                actor_agent_id=agent,
            )

        await self._graph.emit_event(
            organization_id=org_id,
            study_id=study_id,
            event_type="SYNTHETIC_DATA_RUN_COMPLETED",
            actor_agent_id=agent,
            ai_decision_id=decision_id,
            node_id=run_node.id,
            payload={
                "run_id": str(run.id),
                "target_n": target_n,
                "random_seed": random_seed,
                "label": "SYNTHETIC",
                "output_artifact_id": str(output_artifact.id),
            },
        )

    async def _latest_artifact(
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

    async def _artifact_content(self, artifact: Artifact | None) -> dict | None:
        if artifact is None or artifact.current_version_id is None:
            return None
        result = await self._db.execute(
            select(ArtifactVersion).where(
                ArtifactVersion.id == artifact.current_version_id
            )
        )
        version = result.scalar_one_or_none()
        return version.content if version else None

    def _build_assumptions(
        self,
        run: SyntheticDataRun,
        study: Study,
        protocol_content: dict | None,
        sap_content: dict | None,
        edc_content: dict | None,
        target_n: int,
        random_seed: int,
    ) -> list[SimulationAssumption]:
        assumptions = [
            SimulationAssumption(
                organization_id=study.organization_id,
                run_id=run.id,
                assumption_type="SAMPLE_SIZE",
                domain="DM",
                variable="N",
                description=f"Generate {target_n} synthetic subjects",
                rationale="User-specified sample size for MVP synthetic cohort",
                parameters={"target_n": target_n},
                source_reference="synthetic_data_service.create_run",
            ),
            SimulationAssumption(
                organization_id=study.organization_id,
                run_id=run.id,
                assumption_type="RANDOM_SEED",
                domain=None,
                variable=None,
                description=f"Random seed {random_seed} for reproducibility",
                rationale="Mandatory reproducibility per CIP synthetic data rules",
                parameters={"random_seed": random_seed},
                source_reference="CIP synthetic data invariant",
            ),
        ]
        if protocol_content:
            phase = (protocol_content.get("synopsis") or {}).get("phase") or study.phase
            assumptions.append(
                SimulationAssumption(
                    organization_id=study.organization_id,
                    run_id=run.id,
                    assumption_type="STUDY_DESIGN",
                    domain="DM",
                    description=f"Treatment arms derived from protocol phase {phase}",
                    rationale="Arm allocation follows protocol design",
                    parameters={"phase": str(phase)},
                    source_reference="protocol artifact",
                )
            )
        if sap_content:
            pop = (sap_content.get("analysis_populations") or {}).get(
                "ITT", "ITT population"
            )
            assumptions.append(
                SimulationAssumption(
                    organization_id=study.organization_id,
                    run_id=run.id,
                    assumption_type="ANALYSIS_POPULATION",
                    domain="ADSL",
                    description=f"ITT population definition: {pop}",
                    rationale="Demographics simulated to support SAP ITT population",
                    parameters={"population": pop},
                    source_reference="SAP artifact",
                )
            )
        if edc_content:
            fields = edc_content.get("fields") or []
            assumptions.append(
                SimulationAssumption(
                    organization_id=study.organization_id,
                    run_id=run.id,
                    assumption_type="EDC_FIELD_CATALOG",
                    domain="ECR",
                    description=f"{len(fields)} eCRF fields from EDC specification",
                    rationale="Synthetic values generated for EDC-defined fields",
                    parameters={"field_count": len(fields)},
                    source_reference="EDC_CRF artifact",
                )
            )
        return assumptions

    @staticmethod
    def _rows_to_csv(columns: list[str], rows: list[dict]) -> str:
        """Serialize tabular rows to RFC 4180 CSV text."""
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()

    @classmethod
    def csv_from_content(cls, content: dict, artifact_name: str) -> tuple[str, str]:
        """Resolve CSV filename and body from synthetic artifact content."""
        csv_files = content.get("csv_files") or {}
        primary = content.get("primary_csv_filename")
        if primary and primary in csv_files:
            return primary, csv_files[primary]
        if csv_files:
            filename = next(iter(csv_files))
            return filename, csv_files[filename]

        datasets = content.get("datasets") or {}
        if not datasets:
            raise ValueError("No CSV or tabular dataset found in artifact content.")

        domain_name, domain = next(iter(datasets.items()))
        columns = domain.get("columns") or []
        rows = domain.get("rows") or []
        if not columns or not rows:
            raise ValueError("Synthetic dataset has no exportable rows.")

        slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in artifact_name)
        filename = f"{slug}_{domain_name}.csv"
        return filename, cls._rows_to_csv(columns, rows)

    def _generate_dataset(
        self,
        study: Study,
        target_n: int,
        random_seed: int,
        protocol_content: dict | None,
        sap_content: dict | None,
        edc_content: dict | None,
    ) -> dict:
        rng = random.Random(random_seed)
        arms = ["Placebo", "Active"]
        if protocol_content:
            arms_raw = (protocol_content.get("study_design") or {}).get(
                "treatment_arms"
            )
            if isinstance(arms_raw, list) and arms_raw:
                arms = [str(a) for a in arms_raw[:2]] or arms

        subjects = []
        for i in range(1, target_n + 1):
            arm = arms[i % len(arms)]
            hba1c_bl = round(rng.uniform(5.7, 6.4), 2)
            hba1c_w12 = round(
                hba1c_bl - rng.uniform(0.1, 0.6)
                if arm == "Active"
                else hba1c_bl + rng.uniform(0, 0.2),
                2,
            )
            subjects.append(
                {
                    "SUBJECT_ID": f"{study.protocol_number}-{i:03d}",
                    "SITE_ID": f"{rng.randint(1, 10):03d}",
                    "ARM": arm,
                    "SEX": rng.choice(["M", "F"]),
                    "AGE": rng.randint(30, 75),
                    "RACE": rng.choice(["White", "Black", "Asian", "Other"]),
                    "ETHNICITY": rng.choice(["Hispanic", "Not Hispanic"]),
                    "BMI": round(rng.uniform(22, 35), 1),
                    "HBA1C_BL": hba1c_bl,
                    "HBA1C_W12": hba1c_w12,
                    "FASTING_GLUCOSE_BL": rng.randint(100, 125),
                    "SYSBP": rng.randint(110, 140),
                    "DIABP": rng.randint(70, 90),
                    "HR": rng.randint(60, 90),
                    "AE_FLAG": rng.choice(["Y", "N"]),
                    "COMPLIANCE_PERCENT": rng.randint(80, 100),
                    "ENDPOINT_DELTA_HBA1C": round(hba1c_w12 - hba1c_bl, 2),
                }
            )

        columns = [
            "SUBJECT_ID",
            "SITE_ID",
            "ARM",
            "SEX",
            "AGE",
            "RACE",
            "ETHNICITY",
            "BMI",
            "HBA1C_BL",
            "HBA1C_W12",
            "FASTING_GLUCOSE_BL",
            "SYSBP",
            "DIABP",
            "HR",
            "AE_FLAG",
            "COMPLIANCE_PERCENT",
            "ENDPOINT_DELTA_HBA1C",
        ]
        csv_filename = f"{study.protocol_number}_synthetic_demographics.csv"
        csv_body = self._rows_to_csv(columns, subjects)

        return {
            "label": "SYNTHETIC",
            "document_type": "RAW_CLINICAL_DATA",
            "format": "CSV",
            "description": (
                f"Synthetic patient-level CSV for {study.name}. "
                "NOT derived from real patients."
            ),
            "random_seed": random_seed,
            "synthetic_flag": "Y",
            "source_system": "Celerius Synthetic Data Generator",
            "record_counts": {"subjects": target_n},
            "primary_csv_filename": csv_filename,
            "csv_files": {csv_filename: csv_body},
            "inputs_used": {
                "protocol": protocol_content is not None,
                "sap": sap_content is not None,
                "edc_crf": edc_content is not None,
            },
            "datasets": {
                "demographics": {
                    "columns": columns,
                    "row_count": target_n,
                    "rows": subjects,
                },
            },
        }
