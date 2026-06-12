"""Unit tests for CSR section prose generation."""

from __future__ import annotations

import pytest

from app.services.generators.csr_generator import CSRGenerator


@pytest.mark.asyncio
async def test_generate_section_prose_deterministic_without_api_key():
    context = {
        "section_title": "Efficacy Evaluation",
        "study_name": "Demo Study",
        "protocol_number": "DEMO-001",
        "protocol_excerpt": {"objectives_primary": ["Improve PFS"]},
        "sap_excerpt": {"primary_endpoint": "Progression-free survival"},
        "tlf_tables": [{"id": "T-01", "title": "Efficacy table"}],
    }

    prose = await CSRGenerator.generate_section_prose(
        "13",
        context,
        api_key=None,
    )

    assert "Progression-free survival" in prose
    assert "T-01" in prose
    assert len(prose.split()) > 20
