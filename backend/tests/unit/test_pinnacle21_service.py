"""Unit tests for Pinnacle 21 validation adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.services.pinnacle21_service import Pinnacle21Service


def _settings(*, enabled: bool = True):
    s = MagicMock()
    s.pinnacle21_configured = enabled
    s.PINNACLE21_ENABLED = enabled
    s.PINNACLE21_API_KEY = "test-key" if enabled else ""
    s.PINNACLE21_API_BASE_URL = "https://api.pinnacle21.test"
    s.PINNACLE21_PROJECT_ID = "proj-1"
    s.PINNACLE21_RULE_SET_VERSION = "CE 3.1"
    s.SDTM_IG_VERSION = "3.3"
    return s


@pytest.mark.asyncio
class TestPinnacle21Service:
    async def test_disabled_flag_skips_http(self):
        db = AsyncMock()
        svc = Pinnacle21Service(db, _settings(enabled=False))
        findings = await svc.validate_sdtm_dataset(
            dataset_path="/tmp/dm.xpt",
            ig_version="3.3",
            rule_set="CE 3.1",
            organization_id=uuid4(),
            study_id=uuid4(),
            validation_run_id=uuid4(),
            artifact_id=uuid4(),
            actor=None,
        )
        assert findings == []

    async def test_successful_validation_records_evidence(self):
        db = AsyncMock()
        settings = _settings(enabled=True)
        svc = Pinnacle21Service(db, settings)
        svc._validation_intel.record_evidence = AsyncMock()
        svc._ai_decision.begin_decision = AsyncMock(return_value=MagicMock(id=uuid4()))
        svc._ai_decision.complete_decision = AsyncMock()

        from app.services.pinnacle21_service import P21Finding

        actor = MagicMock()
        actor.id = uuid4()
        actor.organization_id = uuid4()

        with patch.object(
            svc,
            "_call_p21_api",
            new_callable=AsyncMock,
            return_value=[
                P21Finding(
                    rule_id="P21-DM-001",
                    rule_name="STUDYID required",
                    severity="ERROR",
                    message="STUDYID missing",
                    status="FAIL",
                )
            ],
        ):
            findings = await svc.validate_sdtm_dataset(
                dataset_path="artifact:abc",
                ig_version="3.3",
                rule_set="CE 3.1",
                organization_id=actor.organization_id,
                study_id=uuid4(),
                validation_run_id=uuid4(),
                artifact_id=uuid4(),
                actor=actor,
            )

        assert len(findings) == 1
        assert findings[0].rule_id == "P21-DM-001"
        svc._validation_intel.record_evidence.assert_called_once()
        call_kwargs = svc._validation_intel.record_evidence.call_args.kwargs
        assert call_kwargs["source"] == "PINNACLE21"

    async def test_api_error_does_not_raise(self):
        db = AsyncMock()
        settings = _settings(enabled=True)
        svc = Pinnacle21Service(db, settings)
        svc._ai_decision.begin_decision = AsyncMock(return_value=MagicMock(id=uuid4()))
        svc._ai_decision.complete_decision = AsyncMock()

        actor = MagicMock()
        actor.organization_id = uuid4()

        with patch.object(
            svc,
            "_call_p21_api",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "Service unavailable",
                request=httpx.Request("POST", "https://api.pinnacle21.test/v1/validate"),
                response=httpx.Response(503),
            ),
        ):
            findings = await svc.validate_sdtm_dataset(
                dataset_path="artifact:abc",
                ig_version="3.3",
                rule_set="CE 3.1",
                organization_id=actor.organization_id,
                study_id=uuid4(),
                validation_run_id=uuid4(),
                artifact_id=uuid4(),
                actor=actor,
            )

        assert findings == []
        svc._ai_decision.complete_decision.assert_called_once()
