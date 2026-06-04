"""Protocol document generator."""

from __future__ import annotations

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob
from app.services.generators.base_generator import BaseGenerator

_SYSTEM = """You are a clinical trial protocol writer with deep expertise in ICH E6(R2) GCP and regulatory submission standards.

Your task is to generate a structured clinical trial protocol in valid JSON format. The output must be a single JSON object — no prose outside the JSON.

Required fields:
{
  "document_type": "PROTOCOL",
  "version": "1.0",
  "title": "<full protocol title>",
  "protocol_number": "<number>",
  "synopsis": {
    "title": "", "sponsor": "", "indication": "", "phase": "",
    "design": "", "primary_objective": "", "primary_endpoint": "",
    "sample_size": "", "duration": "", "regimens": []
  },
  "objectives": {
    "primary": "<primary objective>",
    "secondary": ["<objective>"],
    "exploratory": ["<objective>"]
  },
  "study_design": {
    "type": "", "blinding": "", "randomization": "",
    "treatment_arms": [], "duration_weeks": null,
    "follow_up_weeks": null
  },
  "eligibility": {
    "inclusion_criteria": ["<criterion>"],
    "exclusion_criteria": ["<criterion>"]
  },
  "study_procedures": ["<procedure>"],
  "endpoints": {
    "primary": {"name": "", "measure": "", "timepoint": ""},
    "secondary": [{"name": "", "measure": "", "timepoint": ""}]
  },
  "statistical_considerations": {
    "sample_size_rationale": "",
    "primary_analysis": "",
    "alpha": 0.05,
    "power": 0.80
  },
  "safety_monitoring": {
    "dsmb": false,
    "stopping_rules": []
  },
  "regulatory_references": ["ICH E6(R2)", "ICH E9", "21 CFR Part 312"]
}"""


class ProtocolGenerator(BaseGenerator):
    ARTIFACT_TYPE = ArtifactType.PROTOCOL
    AGENT_NAME = "protocol-generator"

    def _artifact_name(self, study_name: str) -> str:
        return f"{study_name} — Clinical Trial Protocol v1.0"

    async def _build_content(
        self, job: GenerationJob, study: object, model_id: str
    ) -> dict:
        ctx = job.input_context or {}
        user_prompt = f"""Generate a complete clinical trial protocol for the following study.

Study details:
- Name: {study.name}
- Protocol Number: {study.protocol_number}
- Indication: {ctx.get("indication") or getattr(study, "indication", "Not specified")}
- Therapeutic Area: {ctx.get("therapeutic_area") or getattr(study, "therapeutic_area", "Not specified")}
- Phase: {ctx.get("phase") or getattr(study, "phase", "Not specified")}
- Sponsor: {ctx.get("sponsor") or getattr(study, "sponsor", "Not specified")}
- Primary Objective: {ctx.get("primary_objective", "Evaluate efficacy and safety")}
- Treatment Arms: {ctx.get("treatment_arms", "To be specified")}
- Additional context: {ctx.get("additional_context", "")}

Return only valid JSON matching the required schema."""

        text = await self._call_claude(
            system_prompt=_SYSTEM, user_prompt=user_prompt, model_id=model_id
        )
        return self._parse_json_response(text)
