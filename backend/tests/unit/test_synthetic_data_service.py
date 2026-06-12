"""Unit tests for synthetic data service MVP generation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.user import Role
from app.services.synthetic_data_service import SyntheticDataService


def _make_study():
    study = MagicMock()
    study.id = uuid4()
    study.organization_id = uuid4()
    study.name = "Test Study"
    study.protocol_number = "TST-001"
    study.phase = MagicMock(value="Phase II")
    return study


def _make_actor(org_id, role: Role = Role.CONTRIBUTOR):
    actor = MagicMock()
    actor.id = uuid4()
    actor.organization_id = org_id
    actor.effective_role = role
    return actor


class TestSyntheticDataServiceDataset:
    def test_generate_dataset_labels_synthetic(self):
        svc = SyntheticDataService(MagicMock())
        study = _make_study()
        dataset = svc._generate_dataset(
            study=study,
            target_n=10,
            random_seed=42,
            protocol_content=None,
            sap_content=None,
            edc_content=None,
        )

        assert dataset["label"] == "SYNTHETIC"
        assert dataset["format"] == "CSV"
        assert dataset["synthetic_flag"] == "Y"
        assert dataset["random_seed"] == 42
        assert dataset["record_counts"]["subjects"] == 10
        assert len(dataset["datasets"]["demographics"]["rows"]) == 10
        assert "HBA1C_BL" in dataset["datasets"]["demographics"]["columns"]
        assert "csv_files" in dataset
        csv_name = dataset["primary_csv_filename"]
        csv_body = dataset["csv_files"][csv_name]
        assert csv_body.startswith("SUBJECT_ID,SITE_ID,ARM")
        assert csv_body.count("\n") == 11

    def test_csv_from_content_legacy_json(self):
        svc = SyntheticDataService(MagicMock())
        content = {
            "datasets": {
                "demographics": {
                    "columns": ["SUBJECT_ID", "ARM"],
                    "rows": [{"SUBJECT_ID": "001", "ARM": "Active"}],
                }
            }
        }
        filename, body = svc.csv_from_content(content, "Study Synthetic Data")
        assert filename.endswith(".csv")
        assert "SUBJECT_ID,ARM" in body
        assert "001,Active" in body

    def test_reproducible_with_same_seed(self):
        svc = SyntheticDataService(MagicMock())
        study = _make_study()
        d1 = svc._generate_dataset(study, 5, 99, None, None, None)
        d2 = svc._generate_dataset(study, 5, 99, None, None, None)
        assert d1["datasets"]["demographics"]["rows"] == d2["datasets"]["demographics"]["rows"]

    def test_build_assumptions_includes_seed_and_n(self):
        svc = SyntheticDataService(MagicMock())
        study = _make_study()
        run = MagicMock()
        run.id = uuid4()
        assumptions = svc._build_assumptions(
            run=run,
            study=study,
            protocol_content={"synopsis": {"phase": "II"}},
            sap_content={"analysis_populations": {"ITT": "All randomized"}},
            edc_content={"fields": [{"field_id": "HBA1C"}]},
            target_n=50,
            random_seed=7,
        )
        types = {a.assumption_type for a in assumptions}
        assert "SAMPLE_SIZE" in types
        assert "RANDOM_SEED" in types
        assert "STUDY_DESIGN" in types
        assert "ANALYSIS_POPULATION" in types
        assert "EDC_FIELD_CATALOG" in types


@pytest.mark.asyncio
class TestSyntheticDataServiceCreateRun:
    async def test_create_run_requires_sap(self):
        svc = SyntheticDataService(MagicMock())
        study = _make_study()
        actor = _make_actor(study.organization_id)

        svc._study_repo.get = AsyncMock(return_value=study)
        svc._latest_artifact = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await svc.create_run(
                study_id=study.id,
                target_n=10,
                random_seed=42,
                actor=actor,
            )

        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "SAP_REQUIRED"


@pytest.mark.asyncio
class TestSyntheticGraphRegistration:
    async def test_register_synthetic_graph_creates_run_node(self):
        svc = SyntheticDataService(MagicMock())
        org_id = uuid4()
        study = _make_study()
        actor = _make_actor(org_id)
        run = MagicMock()
        run.id = uuid4()
        run.run_name = "Synthetic Run"
        run.description = "Test run"
        run.status = "COMPLETED"
        output = MagicMock()
        output.id = uuid4()
        output.name = "Synthetic Output"
        output.artifact_type = MagicMock(value="OTHER")
        assumption = MagicMock()
        assumption.id = uuid4()
        assumption.description = "Seed assumption"
        assumption.assumption_type = "RANDOM_SEED"
        assumption.domain = None

        svc._graph.register_domain_record = AsyncMock(
            side_effect=[
                (MagicMock(id=uuid4()), None),
                (MagicMock(id=uuid4()), None),
                (MagicMock(id=uuid4()), None),
                (MagicMock(id=uuid4()), None),
                (MagicMock(id=uuid4()), None),
            ]
        )
        svc._graph.create_relationship = AsyncMock()
        svc._graph.emit_event = AsyncMock()

        await svc._register_synthetic_graph(
            run=run,
            study=study,
            output_artifact=output,
            decision_id=uuid4(),
            actor=actor,
            protocol=None,
            sap=None,
            edc=None,
            assumptions=[assumption],
            target_n=10,
            random_seed=42,
        )

        assert svc._graph.register_domain_record.await_count >= 4
        svc._graph.emit_event.assert_called_once()
        assert (
            svc._graph.emit_event.call_args.kwargs["event_type"]
            == "SYNTHETIC_DATA_RUN_COMPLETED"
        )
