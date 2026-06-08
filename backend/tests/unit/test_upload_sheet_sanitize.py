"""Unit tests for Excel sheet name sanitization."""

from __future__ import annotations

from app.services.upload_service import UploadService


class TestSanitizeSheetName:
    def test_strips_and_replaces_invalid_chars(self):
        assert UploadService._sanitize_sheet_name("  Demographics/Data  ") == "Demographics_Data"

    def test_empty_becomes_sheet(self):
        assert UploadService._sanitize_sheet_name("///") == "Sheet"

    def test_truncates_long_names(self):
        long_name = "A" * 150
        assert len(UploadService._sanitize_sheet_name(long_name)) == 100
