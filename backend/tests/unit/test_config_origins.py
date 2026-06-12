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


class TestTrustedProxies:
    def test_parses_comma_separated_ips_and_networks(self):
        settings = Settings.model_construct(
            TRUSTED_PROXIES="10.0.0.1, 192.168.0.0/16,2001:db8::/32"
        )

        assert settings.trusted_proxies == [
            "10.0.0.1",
            "192.168.0.0/16",
            "2001:db8::/32",
        ]

    def test_empty_value_disables_forwarded_header_trust(self):
        settings = Settings.model_construct(TRUSTED_PROXIES="")

        assert settings.trusted_proxies == []
