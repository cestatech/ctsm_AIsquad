"""
Protocol Generator — Placeholder Service

Implements the AIGenerationService interface with a mock response.
Replace this implementation in Phase 7 with the real LLM-powered generator.

The placeholder validates inputs, logs the job, and returns a realistic mock
draft that demonstrates the intended data flow.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactType
from app.models.user import User


MOCK_PROTOCOL_TEMPLATE = {
    "version": "placeholder-v1.0",
    "sections": {
        "title_page": {
            "protocol_title": "{study_name}",
            "protocol_number": "{protocol_number}",
            "sponsor": "{sponsor}",
            "phase": "{phase}",
            "indication": "{indication}",
            "version": "1.0 DRAFT",
            "date": "{generation_date}",
        },
        "synopsis": {
            "title": "Protocol Synopsis",
            "content": "AI-generated placeholder synopsis. Replace in Phase 7.",
        },
        "background": {
            "title": "1. Background and Rationale",
            "content": "AI-generated placeholder background. Replace in Phase 7.",
        },
        "objectives": {
            "title": "2. Study Objectives and Endpoints",
            "primary_objective": "To be defined based on study concept.",
            "primary_endpoint": "To be defined based on study concept.",
            "secondary_objectives": [],
            "secondary_endpoints": [],
        },
        "study_design": {
            "title": "3. Study Design",
            "content": "AI-generated placeholder design. Replace in Phase 7.",
        },
        "population": {
            "title": "4. Study Population",
            "inclusion_criteria": ["Criterion 1 (placeholder)"],
            "exclusion_criteria": ["Criterion 1 (placeholder)"],
        },
        "statistical_considerations": {
            "title": "8. Statistical Considerations",
            "content": "Statistical section to be completed by SAP. Placeholder.",
        },
    },
    "_generation_metadata": {
        "is_placeholder": True,
        "generated_by": "protocol_agent_placeholder_v1",
        "note": "This is a placeholder draft. Phase 7 will generate real content.",
    },
}


async def generate_protocol_draft(
    db: AsyncSession,
    organization_id: UUID,
    study_id: UUID,
    user: User,
    context: dict,
) -> dict:
    """
    Placeholder implementation. Returns a mock protocol draft after a short delay
    to simulate async generation.

    In Phase 7, this will be replaced with a real LLM call using the assembled
    context (study metadata, indication, regulatory region, etc.).
    """
    # Simulate processing time
    await asyncio.sleep(1)

    study_name = context.get("study_name", "Study Name TBD")
    protocol_number = context.get("protocol_number", "PROTOCOL-001")

    content = json.loads(json.dumps(MOCK_PROTOCOL_TEMPLATE))
    content["sections"]["title_page"]["protocol_title"] = study_name
    content["sections"]["title_page"]["protocol_number"] = protocol_number
    content["sections"]["title_page"]["sponsor"] = context.get("sponsor", "Sponsor TBD")
    content["sections"]["title_page"]["phase"] = context.get("phase", "TBD")
    content["sections"]["title_page"]["indication"] = context.get("indication", "TBD")
    content["sections"]["title_page"]["date"] = datetime.now(UTC).strftime("%Y-%m-%d")
    content["_generation_metadata"]["generated_at"] = datetime.now(UTC).isoformat()
    content["_generation_metadata"]["context_hash"] = hashlib.sha256(
        json.dumps(context, sort_keys=True).encode()
    ).hexdigest()

    return content
