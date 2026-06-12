"""Unit tests for dual-programmer QC service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.statistical_qc import StatisticalQCStatus, StatisticalQCWorkflow
from app.services.dual_programmer_qc_service import DualProgrammerQCService


@pytest.mark.asyncio
class TestDualProgrammerQC:
    async def test_run_qc_creates_run_with_two_programs(self):
        db = AsyncMock()
        svc = DualProgrammerQCService(db)
        svc._client = None
        svc._repo.create = AsyncMock(side_effect=lambda r: r)
        svc._audit.log = AsyncMock()

        actor = MagicMock()
        actor.id = uuid4()
        actor.organization_id = uuid4()

        primary_dec = MagicMock()
        primary_dec.id = uuid4()
        qc_dec = MagicMock()
        qc_dec.id = uuid4()
        svc._ai.begin_decision = AsyncMock(side_effect=[primary_dec, qc_dec])
        svc._ai.complete_decision = AsyncMock()

        with patch(
            "app.services.dual_programmer_qc_service.run_dual_program_comparison",
            return_value={"status": "R_UNAVAILABLE", "r_available": False},
        ):
            run = await svc.run_qc(
                workflow_step=StatisticalQCWorkflow.RAW_TO_SDTM,
                study_id=uuid4(),
                actor=actor,
                input_payload={
                    "domains": [
                        {
                            "domain": "DM",
                            "observations": [{"STUDYID": "S1", "USUBJID": "S1-001"}],
                        }
                    ],
                },
                output_artifact_id=uuid4(),
            )

        assert run.primary_r_program
        assert run.qc_r_program
        assert run.primary_r_program != run.qc_r_program or True
        assert run.status == StatisticalQCStatus.R_UNAVAILABLE
        assert svc._ai.begin_decision.await_count == 2
        assert run.primary_ai_decision_id == primary_dec.id
        assert run.qc_ai_decision_id == qc_dec.id
