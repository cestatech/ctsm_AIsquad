"""Unit tests for PHI sample-value masking."""

from __future__ import annotations

from app.core.phi_masking import mask_sample_value, mask_sample_values


class TestPhiMasking:
    def test_masks_phi_column_names(self):
        assert mask_sample_value("patient_name", "John Doe") == "[MASKED]"

    def test_masks_email_values(self):
        assert mask_sample_value("notes", "user@example.com") == "[MASKED]"

    def test_preserves_non_phi_values(self):
        assert mask_sample_value("treatment", "Arm A") == "Arm A"

    def test_caps_sample_list_length(self):
        values = mask_sample_values("age", ["45", "52", "38", "41"])
        assert len(values) == 3
