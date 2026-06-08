"""Unit tests for base generator model normalization."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.generators.sap_generator import SAPGenerator


class TestBaseGeneratorModelNormalization:
    def test_normalizes_legacy_sonnet_alias(self):
        gen = SAPGenerator(MagicMock())
        assert gen._normalize_model_id("claude-sonnet") == "claude-sonnet-4-6"

    def test_passes_through_explicit_model(self):
        gen = SAPGenerator(MagicMock())
        assert gen._normalize_model_id("claude-sonnet-4-6") == "claude-sonnet-4-6"
