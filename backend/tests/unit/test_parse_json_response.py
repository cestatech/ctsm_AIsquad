"""Unit tests for base generator JSON parsing helpers."""

from __future__ import annotations

import pytest

from app.services.generators.base_generator import BaseGenerator


class TestParseJsonResponse:
    def test_parses_fenced_json(self):
        raw = '```json\n{"document_type": "SAP", "version": "1.0"}\n```'
        result = BaseGenerator._parse_json_response(raw)
        assert result["document_type"] == "SAP"

    def test_strips_trailing_commas(self):
        raw = '{"sections": {"ITT": "all subjects",}, "software": ["SAS",],}'
        result = BaseGenerator._parse_json_response(raw)
        assert result["sections"]["ITT"] == "all subjects"
        assert result["software"] == ["SAS"]

    def test_closes_truncated_object(self):
        raw = '{"document_type": "SAP", "title": "Test SAP", "software": ["SAS"'
        result = BaseGenerator._parse_json_response(raw)
        assert result["document_type"] == "SAP"
        assert result["software"] == ["SAS"]

    def test_raises_on_garbage(self):
        with pytest.raises(ValueError, match="Could not parse JSON"):
            BaseGenerator._parse_json_response("not json at all")
