"""
Seed complete demo programs: intake, protocol, ICF, SAP, eCRF, synthetic data.

Supports DEMO-001 (oncology) and DEMO-002 (rheumatoid arthritis) as separate studies.

Usage (from repo root / Docker backend):
    python /database/seeds/demo_program_seed.py
    python /database/seeds/demo_program_seed.py --protocol DEMO-002
    python /database/seeds/demo_program_seed.py --all
    python /database/seeds/demo_program_seed.py --protocol DEMO-002 --force
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.artifact import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.models.generation import GenerationJob, GenerationJobStatus
from app.models.graph import GraphEdgeType, GraphNodeType
from app.models.intake import IntakeMessage, IntakeStatus, SponsorIntake, StudyBrief
from app.models.intelligence import SimulationAssumption, SyntheticDataRun
from app.models.organization import Organization
from app.models.raw_data import RawDataset, RawField
from app.models.study import Study, StudyPhase, StudyStatus
from app.models.upload import UploadedFile
from app.models.user import User
from app.services.context_graph_service import ContextGraphService
from demo_profiles import ALL_DOMAINS, DEMO_MARKER, DEMO_PROFILES, DemoProfile, get_profile

DOC_TYPES = (
    ArtifactType.PROTOCOL,
    ArtifactType.ICF,
    ArtifactType.SAP,
    ArtifactType.EDC_CRF,
)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed full demo program studies")
    parser.add_argument(
        "--protocol",
        default="DEMO-001",
        help="Protocol number to seed (DEMO-001 or DEMO-002)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Seed all registered demo programs",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-seed even if demo_program_seeded flag is already set",
    )
    args = parser.parse_args()

    protocols = list(DEMO_PROFILES.keys()) if args.all else [args.protocol.upper()]

    settings = get_settings()
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    all_lines: list[str] = []
    async with factory() as session:
        async with session.begin():
            for protocol in protocols:
                lines = await seed_demo_program(session, protocol, force=args.force)
                all_lines.extend(lines)
                all_lines.append("")

    await engine.dispose()
    print("Demo program seed complete.")
    for line in all_lines:
        if line:
            print(f"  {line}")


async def seed_demo_program(
    db: AsyncSession, protocol_number: str, *, force: bool = False
) -> list[str]:
    """Seed or refresh one demo program study."""
    profile = get_profile(protocol_number)
    org = await _lookup_org(db)
    admin = await _lookup_admin(db, org.id)
    study = await _ensure_study(db, org.id, admin.id, profile)

    meta = dict(study.extra_data or {})
    if meta.get("demo_program_seeded") and not force:
        return [
            f"{profile.protocol_number} already seeded (use --force to refresh)",
            f"Study ID: {study.id}",
        ]

    await _clear_demo_data(db, study.id, org.id)
    await _update_study_metadata(db, study, profile)

    intake = await _seed_intake(db, org.id, study.id, admin.id, profile)
    brief = await _seed_brief(db, org.id, study.id, admin.id, intake.id, profile)

    artifacts = await _seed_document_artifacts(db, org.id, study, admin, profile)
    synthetic_artifact = await _seed_synthetic_artifact(db, org.id, study, admin, profile)
    await _seed_synthetic_raw_upload(db, org.id, study, admin, profile)
    await _seed_generation_jobs(db, org.id, study.id, admin.id, brief.id, artifacts)
    await _seed_synthetic_run(db, org.id, study.id, admin.id, synthetic_artifact.id, profile)
    await _seed_graph(db, org.id, study, admin, intake, brief, artifacts)

    study.extra_data = {**meta, "demo_program_seeded": DEMO_MARKER}
    await db.flush()

    return [
        f"Study: {profile.protocol_number} — {study.name}",
        f"Study ID: {study.id}",
        f"Intake: COMPILED ({len(ALL_DOMAINS)}/9 domains)",
        f"Artifacts: PROTOCOL, ICF, SAP, EDC_CRF, Synthetic raw data",
        f"Synthetic run: {profile.synthetic_run['run_name']}",
        "→ Intake, Artifacts, EDC Screens, Intelligence → Synthetic Data",
    ]


async def _lookup_org(db: AsyncSession) -> Organization:
    result = await db.execute(
        select(Organization).where(Organization.slug == "demo-pharma")
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise RuntimeError(
            "Demo org not found. Run dev_seed.py first: "
            "python /database/seeds/dev_seed.py"
        )
    return org


async def _lookup_admin(db: AsyncSession, org_id) -> User:
    result = await db.execute(
        select(User).where(
            User.organization_id == org_id,
            User.email == "admin@demo.dev",
        )
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        raise RuntimeError("admin@demo.dev not found. Run dev_seed.py first.")
    return admin


async def _ensure_study(
    db: AsyncSession, org_id, admin_id, profile: DemoProfile
) -> Study:
    """Find or create the study shell for a demo protocol."""
    result = await db.execute(
        select(Study).where(
            Study.organization_id == org_id,
            Study.protocol_number == profile.protocol_number,
        )
    )
    study = result.scalar_one_or_none()
    if study is not None:
        return study

    study = Study(
        id=uuid4(),
        organization_id=org_id,
        protocol_number=profile.protocol_number,
        name=profile.study_name,
        description=profile.study_meta.get("description"),
        status=StudyStatus.ACTIVE,
        created_by_id=admin_id,
    )
    db.add(study)
    await db.flush()
    return study


async def _clear_demo_data(db: AsyncSession, study_id, org_id) -> None:
    """Remove prior demo-program entities so re-run is idempotent."""
    await db.execute(
        delete(SimulationAssumption).where(
            SimulationAssumption.run_id.in_(
                select(SyntheticDataRun.id).where(
                    SyntheticDataRun.study_id == study_id,
                    SyntheticDataRun.organization_id == org_id,
                )
            )
        )
    )
    await db.execute(
        delete(SyntheticDataRun).where(
            SyntheticDataRun.study_id == study_id,
            SyntheticDataRun.organization_id == org_id,
        )
    )
    await db.execute(
        delete(GenerationJob).where(
            GenerationJob.study_id == study_id,
            GenerationJob.organization_id == org_id,
            GenerationJob.artifact_type.in_(DOC_TYPES),
        )
    )

    intake_ids = (
        await db.execute(
            select(SponsorIntake.id).where(SponsorIntake.study_id == study_id)
        )
    ).scalars().all()
    if intake_ids:
        await db.execute(
            delete(IntakeMessage).where(IntakeMessage.intake_id.in_(intake_ids))
        )
        await db.execute(delete(StudyBrief).where(StudyBrief.intake_id.in_(intake_ids)))
        await db.execute(delete(SponsorIntake).where(SponsorIntake.id.in_(intake_ids)))

    upload_ids = (
        await db.execute(
            select(UploadedFile.id).where(
                UploadedFile.study_id == study_id,
                UploadedFile.organization_id == org_id,
                UploadedFile.description.like(f"%{DEMO_MARKER}%"),
            )
        )
    ).scalars().all()
    if upload_ids:
        dataset_ids = (
            await db.execute(
                select(RawDataset.id).where(
                    RawDataset.uploaded_file_id.in_(upload_ids),
                    RawDataset.organization_id == org_id,
                )
            )
        ).scalars().all()
        if dataset_ids:
            await db.execute(
                delete(RawField).where(
                    RawField.raw_dataset_id.in_(dataset_ids),
                    RawField.organization_id == org_id,
                )
            )
            await db.execute(
                delete(RawDataset).where(
                    RawDataset.id.in_(dataset_ids),
                    RawDataset.organization_id == org_id,
                )
            )
        await db.execute(
            delete(UploadedFile).where(
                UploadedFile.id.in_(upload_ids),
                UploadedFile.organization_id == org_id,
            )
        )

    demo_artifact_ids = (
        await db.execute(
            select(Artifact.id).where(
                Artifact.study_id == study_id,
                Artifact.organization_id == org_id,
                Artifact.deleted_at.is_(None),
                Artifact.artifact_type.in_(
                    [*DOC_TYPES, ArtifactType.OTHER, ArtifactType.SDTM_DATASET]
                ),
                Artifact.description.like(f"%{DEMO_MARKER}%"),
            )
        )
    ).scalars().all()
    if demo_artifact_ids:
        # artifact_versions are append-only; soft-delete prior demo artifacts instead.
        await db.execute(
            update(Artifact)
            .where(Artifact.id.in_(demo_artifact_ids))
            .values(deleted_at=datetime.now(UTC))
        )


async def _update_study_metadata(
    db: AsyncSession, study: Study, profile: DemoProfile
) -> None:
    meta = profile.study_meta
    study.name = profile.study_name
    study.indication = meta["indication"]
    study.therapeutic_area = meta["therapeutic_area"]
    study.phase = StudyPhase(meta["phase"])
    study.sponsor = meta["sponsor"]
    study.short_name = meta["short_name"]
    study.description = meta["description"]
    await db.flush()


async def _seed_intake(
    db: AsyncSession, org_id, study_id, admin_id, profile: DemoProfile
) -> SponsorIntake:
    intake = SponsorIntake(
        id=uuid4(),
        organization_id=org_id,
        study_id=study_id,
        created_by_id=admin_id,
        status=IntakeStatus.COMPILED,
        domains_completed=list(ALL_DOMAINS),
        ready_to_compile=True,
    )
    db.add(intake)
    await db.flush()

    for msg in profile.intake_conversation:
        db.add(
            IntakeMessage(
                id=uuid4(),
                intake_id=intake.id,
                organization_id=org_id,
                role=msg["role"],
                content=msg["content"],
                domain=msg.get("domain"),
                is_hidden=False,
            )
        )
    await db.flush()
    return intake


async def _seed_brief(
    db: AsyncSession, org_id, study_id, admin_id, intake_id, profile: DemoProfile
) -> StudyBrief:
    brief = StudyBrief(
        id=uuid4(),
        intake_id=intake_id,
        organization_id=org_id,
        study_id=study_id,
        compiled_by_id=admin_id,
        content=profile.study_brief,
    )
    db.add(brief)
    await db.flush()
    return brief


def _hash_content(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


async def _create_artifact(
    db: AsyncSession,
    *,
    org_id,
    study: Study,
    admin: User,
    artifact_type: ArtifactType,
    name: str,
    content: dict,
    description: str,
) -> Artifact:
    artifact = Artifact(
        id=uuid4(),
        organization_id=org_id,
        study_id=study.id,
        artifact_type=artifact_type,
        name=name,
        description=description,
        status=ArtifactStatus.DRAFT,
        created_by_id=admin.id,
    )
    db.add(artifact)
    await db.flush()

    version = ArtifactVersion(
        id=uuid4(),
        artifact_id=artifact.id,
        organization_id=org_id,
        version_number=1,
        is_current=True,
        content=content,
        content_hash=_hash_content(content),
        content_diff=None,
        status_at_creation=ArtifactStatus.DRAFT,
        change_summary=f"Demo program seed — {DEMO_MARKER}",
        created_by_id=admin.id,
        created_at=datetime.now(UTC),
    )
    db.add(version)
    await db.flush()

    artifact.current_version_id = version.id
    artifact.current_version_number = 1
    await db.flush()
    return artifact


async def _seed_document_artifacts(
    db: AsyncSession, org_id, study: Study, admin: User, profile: DemoProfile
) -> dict[str, Artifact]:
    study_name = study.name
    desc = f"AI-derived demo document — {DEMO_MARKER}"
    return {
        "PROTOCOL": await _create_artifact(
            db,
            org_id=org_id,
            study=study,
            admin=admin,
            artifact_type=ArtifactType.PROTOCOL,
            name=f"{study_name} — Clinical Trial Protocol v1.0",
            content=profile.protocol_content,
            description=desc,
        ),
        "ICF": await _create_artifact(
            db,
            org_id=org_id,
            study=study,
            admin=admin,
            artifact_type=ArtifactType.ICF,
            name=f"{study_name} — Informed Consent Form v1.0",
            content=profile.icf_content,
            description=desc,
        ),
        "SAP": await _create_artifact(
            db,
            org_id=org_id,
            study=study,
            admin=admin,
            artifact_type=ArtifactType.SAP,
            name=f"{study_name} — Statistical Analysis Plan v1.0",
            content=profile.sap_content,
            description=desc,
        ),
        "EDC_CRF": await _create_artifact(
            db,
            org_id=org_id,
            study=study,
            admin=admin,
            artifact_type=ArtifactType.EDC_CRF,
            name=f"{study_name} — eCRF / EDC Specification v1.0",
            content=profile.edc_crf_content,
            description=desc,
        ),
    }


async def _seed_synthetic_artifact(
    db: AsyncSession, org_id, study: Study, admin: User, profile: DemoProfile
) -> Artifact:
    return await _create_artifact(
        db,
        org_id=org_id,
        study=study,
        admin=admin,
        artifact_type=ArtifactType.OTHER,
        name=f"{study.name} — Synthetic Raw Clinical Data (SYNTHETIC)",
        content=profile.synthetic_dataset_content,
        description=f"Synthetic raw EDC export — {DEMO_MARKER}",
    )


async def _seed_synthetic_raw_upload(
    db: AsyncSession, org_id, study: Study, admin: User, profile: DemoProfile
) -> UploadedFile:
    """Register synthetic output as parsed raw datasets (eCRF form exports)."""
    import openpyxl

    from app.core.config import get_settings

    content = profile.synthetic_dataset_content
    datasets = content.get("datasets", {})
    settings = get_settings()

    stored_filename = f"{uuid4()}_{profile.protocol_number}_SYNTHETIC_RAW.xlsx"
    org_prefix = (
        Path(settings.STORAGE_LOCAL_PATH)
        / "org"
        / str(org_id)
        / "studies"
        / str(study.id)
        / "uploads"
    )
    org_prefix.mkdir(parents=True, exist_ok=True)
    xlsx_path = org_prefix / stored_filename
    json_path = org_prefix / f"{profile.protocol_number}_SYNTHETIC_RAW_EXPORT.json"
    json_path.write_text(json.dumps(content, indent=2), encoding="utf-8")

    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for sheet_key, sheet in datasets.items():
        form_id = str(sheet.get("form_id", sheet_key))[:31]
        worksheet = workbook.create_sheet(title=form_id)
        columns = sheet.get("columns", [])
        worksheet.append(columns)
        for row in sheet.get("sample_rows", []):
            worksheet.append([row.get(col, "") for col in columns])
    workbook.save(xlsx_path)

    file_bytes = xlsx_path.read_bytes()
    upload = UploadedFile(
        id=uuid4(),
        organization_id=org_id,
        study_id=study.id,
        uploaded_by_id=admin.id,
        original_filename=f"{profile.protocol_number}_SYNTHETIC_RAW_EXPORT.xlsx",
        stored_filename=stored_filename,
        file_path=str(xlsx_path),
        file_size_bytes=len(file_bytes),
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        description=f"Synthetic raw EDC export — {DEMO_MARKER}",
        extracted_metadata={
            "label": "SYNTHETIC",
            "format": "EDC_EXPORT",
            "subjects": content.get("record_counts", {}).get("subjects"),
            "form_entries": content.get("record_counts", {}).get("form_entries"),
            "datasets": list(datasets.keys()),
        },
        file_hash=hashlib.sha256(file_bytes).hexdigest(),
        upload_status="PARSED",
    )
    db.add(upload)
    await db.flush()

    for sheet_name, sheet in datasets.items():
        columns = sheet.get("columns", [])
        sample_rows = sheet.get("sample_rows", [])
        form_id = str(sheet.get("form_id", sheet_name))
        ds = RawDataset(
            id=uuid4(),
            organization_id=org_id,
            study_id=study.id,
            uploaded_file_id=upload.id,
            dataset_name=f"{form_id} — {sheet.get('form_name', sheet_name)}",
            row_count=sheet.get("row_count", len(sample_rows)),
            column_count=len(columns),
            parse_status="PARSED",
        )
        db.add(ds)
        await db.flush()

        for idx, col in enumerate(columns):
            col_values = [
                str(row[col]) for row in sample_rows if col in row and row[col] is not None
            ]
            db.add(
                RawField(
                    id=uuid4(),
                    organization_id=org_id,
                    study_id=study.id,
                    raw_dataset_id=ds.id,
                    column_name=col,
                    column_index=idx,
                    inferred_type="string",
                    sample_values=col_values[:5],
                    missing_count=0,
                    distinct_count=len(set(col_values)) if col_values else 0,
                )
            )
        await db.flush()

    return upload


async def _seed_generation_jobs(
    db: AsyncSession,
    org_id,
    study_id,
    admin_id,
    brief_id,
    artifacts: dict[str, Artifact],
) -> None:
    now = datetime.now(UTC)
    for artifact in artifacts.values():
        job = GenerationJob(
            id=uuid4(),
            organization_id=org_id,
            study_id=study_id,
            artifact_type=artifact.artifact_type,
            status=GenerationJobStatus.COMPLETED,
            model_id="demo-seed",
            input_context={"brief_id": str(brief_id), "source": DEMO_MARKER},
            output_artifact_id=artifact.id,
            started_at=now - timedelta(minutes=5),
            completed_at=now - timedelta(minutes=2),
            triggered_by_id=admin_id,
        )
        db.add(job)
    await db.flush()


async def _seed_synthetic_run(
    db: AsyncSession,
    org_id,
    study_id,
    admin_id,
    output_artifact_id,
    profile: DemoProfile,
) -> SyntheticDataRun:
    now = datetime.now(UTC)
    run_cfg = profile.synthetic_run
    run = SyntheticDataRun(
        id=uuid4(),
        organization_id=org_id,
        study_id=study_id,
        run_name=run_cfg["run_name"],
        description=run_cfg["description"],
        target_n=run_cfg["target_n"],
        target_domains=run_cfg["configuration"]["forms_generated"],
        configuration=run_cfg["configuration"],
        random_seed=run_cfg["random_seed"],
        status="COMPLETED",
        records_generated=run_cfg["target_n"],
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
        output_artifact_id=output_artifact_id,
        created_by_id=admin_id,
    )
    db.add(run)
    await db.flush()

    for assumption in profile.synthetic_assumptions:
        db.add(
            SimulationAssumption(
                id=uuid4(),
                organization_id=org_id,
                run_id=run.id,
                **assumption,
            )
        )
    await db.flush()
    return run


async def _seed_graph(
    db: AsyncSession,
    org_id,
    study: Study,
    admin: User,
    intake: SponsorIntake,
    brief: StudyBrief,
    artifacts: dict[str, Artifact],
) -> None:
    """Register key demo entities in the context graph."""
    graph = ContextGraphService(db)

    study_node, _ = await graph.register_domain_record(
        organization_id=org_id,
        node_type=GraphNodeType.STUDY,
        external_id=study.id,
        external_type="study",
        label=study.name,
        study_id=study.id,
        actor=admin,
    )
    intake_node, _ = await graph.register_domain_record(
        organization_id=org_id,
        node_type=GraphNodeType.INTAKE_SESSION,
        external_id=intake.id,
        external_type="sponsor_intake",
        label=f"Intake: {study.name}",
        study_id=study.id,
        description="Demo program — compiled sponsor intake",
        properties={"status": "COMPILED", "domains_completed": len(ALL_DOMAINS)},
        actor=admin,
    )
    brief_node, _ = await graph.register_domain_record(
        organization_id=org_id,
        node_type=GraphNodeType.STUDY_BRIEF,
        external_id=brief.id,
        external_type="study_brief",
        label=f"Study Brief — {study.protocol_number}",
        study_id=study.id,
        actor=admin,
    )

    await graph.create_relationship(
        organization_id=org_id,
        source_node_id=intake_node.id,
        target_node_id=study_node.id,
        edge_type=GraphEdgeType.PART_OF,
        study_id=study.id,
        actor=admin,
    )
    await graph.create_relationship(
        organization_id=org_id,
        source_node_id=brief_node.id,
        target_node_id=intake_node.id,
        edge_type=GraphEdgeType.DERIVED_FROM,
        study_id=study.id,
        actor=admin,
    )

    type_map = {
        "PROTOCOL": GraphNodeType.PROTOCOL,
        "ICF": GraphNodeType.ARTIFACT,
        "SAP": GraphNodeType.ARTIFACT,
        "EDC_CRF": GraphNodeType.ECR_FORM,
    }
    for key, artifact in artifacts.items():
        art_node, _ = await graph.register_domain_record(
            organization_id=org_id,
            node_type=type_map.get(key, GraphNodeType.ARTIFACT),
            external_id=artifact.id,
            external_type="artifact",
            label=artifact.name,
            study_id=study.id,
            properties={"artifact_type": artifact.artifact_type.value},
            actor=admin,
        )
        await graph.create_relationship(
            organization_id=org_id,
            source_node_id=art_node.id,
            target_node_id=brief_node.id,
            edge_type=GraphEdgeType.GENERATED_FROM,
            study_id=study.id,
            actor=admin,
        )


if __name__ == "__main__":
    asyncio.run(main())
