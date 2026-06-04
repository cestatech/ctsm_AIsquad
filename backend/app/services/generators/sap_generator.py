"""Statistical Analysis Plan (SAP) generator."""

from __future__ import annotations

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob
from app.services.generators.base_generator import BaseGenerator

_SYSTEM = """You are a senior biostatistician with expertise in ICH E9(R1) estimands and regulatory submission standards (FDA, EMA).

Generate a Statistical Analysis Plan as a single JSON object. No prose outside the JSON.

Required schema:
{
  "document_type": "SAP",
  "version": "1.0",
  "title": "<SAP title>",
  "study_design_summary": "<brief summary>",
  "analysis_populations": {
    "ITT": "<definition>",
    "mITT": "<definition or null>",
    "PP": "<definition>",
    "safety": "<definition>"
  },
  "estimands": [
    {
      "name": "Primary estimand",
      "treatment": "", "population": "", "variable": "",
      "intercurrent_events": [], "summary_measure": ""
    }
  ],
  "primary_endpoint_analysis": {
    "endpoint": "", "hypothesis": "", "test": "",
    "covariates": [], "alpha": 0.05, "two_sided": true,
    "multiplicity_adjustment": ""
  },
  "secondary_endpoints": [
    {"endpoint": "", "analysis_method": "", "notes": ""}
  ],
  "subgroup_analyses": ["<subgroup>"],
  "sensitivity_analyses": ["<analysis>"],
  "missing_data": {
    "anticipated_mechanism": "MAR",
    "primary_approach": "",
    "sensitivity_approach": ""
  },
  "interim_analyses": {
    "planned": false,
    "number": 0,
    "stopping_rules": []
  },
  "safety_analyses": {
    "AE_summary": "<approach>",
    "lab_analysis": "<approach>",
    "exposure_analysis": "<approach>"
  },
  "software": ["SAS 9.4", "R 4.3"],
  "regulatory_references": ["ICH E9(R1)", "ICH E3", "FDA SAP Guidance 2019"]
}"""


class SAPGenerator(BaseGenerator):
    ARTIFACT_TYPE = ArtifactType.SAP
    AGENT_NAME = "sap-generator"

    def _artifact_name(self, study_name: str) -> str:
        return f"{study_name} — Statistical Analysis Plan v1.0"

    async def _build_content(self, job: GenerationJob, study: object, model_id: str) -> dict:
        ctx = job.input_context or {}
        user_prompt = f"""Generate a Statistical Analysis Plan for the following clinical trial.

Study details:
- Name: {study.name}
- Protocol Number: {study.protocol_number}
- Indication: {ctx.get("indication") or getattr(study, "indication", "Not specified")}
- Phase: {ctx.get("phase") or getattr(study, "phase", "Not specified")}
- Design: {ctx.get("design", "Randomized, double-blind, placebo-controlled")}
- Primary Endpoint: {ctx.get("primary_endpoint", "To be specified")}
- Secondary Endpoints: {ctx.get("secondary_endpoints", "To be specified")}
- Sample Size: {ctx.get("sample_size", "To be determined")}
- Statistical Method Preferences: {ctx.get("stat_methods", "MMRM for continuous endpoints, logistic regression for binary")}
- Estimand Framework: {ctx.get("estimand_framework", "ICH E9(R1) treatment policy estimand")}

Return only valid JSON."""

        text = await self._call_claude(system_prompt=_SYSTEM, user_prompt=user_prompt, model_id=model_id)
        return self._parse_json_response(text)
