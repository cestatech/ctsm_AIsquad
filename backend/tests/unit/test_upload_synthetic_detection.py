"""Unit tests for synthetic upload detection and labeling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_source import DataSourceType
from app.services.upload_service import UploadService


class TestSyntheticUploadDetection:
    def test_detects_synthetic_from_filename(self):
        assert UploadService._detect_synthetic_upload(
            b"subject_id,age\n001,45",
            "text/csv",
            "CLARITY-50_synthetic_demographics.csv",
        )

    def test_detects_synthetic_from_content_marker(self):
        content = b'label,document_type\nSYNTHETIC,RAW_CLINICAL_DATA\n'
        assert UploadService._detect_synthetic_upload(
            content,
            "text/csv",
            "export.csv",
        )

    def test_live_csv_not_detected_as_synthetic(self):
        content = b"subject_id,age,treatment\nS001,45,A\n"
        assert not UploadService._detect_synthetic_upload(
            content,
            "text/csv",
            "subjects.csv",
        )


@pytest.mark.asyncio
async def test_count_synthetic_uploads():
    svc = UploadService(MagicMock())
    synthetic = MagicMock()
    synthetic.data_source_type = DataSourceType.SYNTHETIC
    synthetic.is_synthetic = True
    live = MagicMock()
    live.data_source_type = DataSourceType.LIVE_FINAL
    live.is_synthetic = False
    svc._repo = AsyncMock()
    svc._repo.list_for_study.return_value = ([synthetic, live, synthetic], 3)
    count = await svc._count_synthetic_uploads(MagicMock(), MagicMock())
    assert count == 2
