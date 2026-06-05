"""Informed Consent Form (ICF) generator."""

from __future__ import annotations

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob
from app.models.study import Study
from app.services.generators.base_generator import BaseGenerator

_SYSTEM = """You are a clinical research expert specialising in informed consent documents compliant with ICH E6(R2), 21 CFR Part 50, and FDA guidance on informed consent.

Generate an ICF as a single JSON object. No prose outside the JSON.

Required schema:
{
  "document_type": "ICF",
  "version": "1.0",
  "title": "<ICF title>",
  "study_summary": "<plain-language summary, ≤150 words>",
  "sections": {
    "introduction": "<text>",
    "purpose": "<text>",
    "number_of_participants": "<text>",
    "study_procedures": ["<procedure>"],
    "risks_and_discomforts": ["<risk>"],
    "potential_benefits": ["<benefit>"],
    "alternatives": "<text>",
    "confidentiality": "<text>",
    "costs_and_compensation": "<text>",
    "injury_treatment": "<text>",
    "voluntary_participation": "<text>",
    "contact_information": {
      "study_questions": "<text>",
      "rights_questions": "<text>",
      "injury_contact": "<text>"
    },
    "authorization": "<HIPAA authorization statement>"
  },
  "readability_level": "8th grade",
  "regulatory_references": ["21 CFR Part 50", "ICH E6(R2)", "45 CFR Part 46"]
}"""


class ICFGenerator(BaseGenerator):
    ARTIFACT_TYPE = ArtifactType.ICF
    AGENT_NAME = "icf-generator"

    def _artifact_name(self, study_name: str) -> str:
        return f"{study_name} — Informed Consent Form v1.0"

    async def _build_content(
        self, job: GenerationJob, study: Study, model_id: str
    ) -> dict:
        ctx = job.input_context or {}
        user_prompt = f"""Generate an Informed Consent Form for the following clinical trial.

Study details:
- Name: {study.name}
- Protocol Number: {study.protocol_number}
- Indication: {ctx.get("indication") or getattr(study, "indication", "Not specified")}
- Phase: {ctx.get("phase") or getattr(study, "phase", "Not specified")}
- Sponsor: {ctx.get("sponsor") or getattr(study, "sponsor", "Not specified")}
- Study Procedures: {ctx.get("procedures", "Study visits, physical examinations, blood draws, study drug administration")}
- Known Risks: {ctx.get("risks", "To be determined based on investigational product profile")}
- Study Duration: {ctx.get("duration", "To be specified")}
- Compensation: {ctx.get("compensation", "No financial compensation for participation")}

Write in plain language at an 8th-grade reading level. Return only valid JSON."""

        text = await self._call_claude(
            system_prompt=_SYSTEM, user_prompt=user_prompt, model_id=model_id
        )
        return self._parse_json_response(text)
