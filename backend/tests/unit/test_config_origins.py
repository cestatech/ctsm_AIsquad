"""Unit tests for CORS origin parsing."""

from __future__ import annotations

from app.core.config import Settings


class TestParseOrigins:
    def test_plain_comma_separated(self):
        result = Settings.parse_origins("http://localhost:3000,http://127.0.0.1:3000")
        assert result == ["http://localhost:3000", "http://127.0.0.1:3000"]

    def test_json_array_string(self):
        result = Settings.parse_origins('["http://localhost:3000"]')
        assert result == ["http://localhost:3000"]

    def test_strips_trailing_slash(self):
        result = Settings.parse_origins("http://localhost:3000/")
        assert result == ["http://localhost:3000"]
