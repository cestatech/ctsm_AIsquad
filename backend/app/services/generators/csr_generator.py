"""Clinical Study Report (CSR) generator."""

from __future__ import annotations

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob
from app.services.generators.base_generator import BaseGenerator

_SYSTEM = """You are a senior medical writer with expertise in ICH E3 Clinical Study Report structure and regulatory submission standards for FDA, EMA, and PMDA.

Generate a CSR outline/shell as a single JSON object following ICH E3 structure. No prose outside the JSON.

Required schema:
{
  "document_type": "CSR",
  "version": "1.0",
  "ich_e3_compliant": true,
  "title": "<full CSR title>",
  "study_identification": {
    "protocol_number": "",
    "sponsor": "",
    "phase": "",
    "indication": "",
    "study_period": {"start": "", "end": ""}
  },
  "synopsis": {
    "objectives": "", "design": "", "population": "",
    "treatments": [], "duration": "",
    "primary_results": "<placeholder — populated post-unblinding>",
    "safety_summary": "<placeholder>",
    "conclusions": "<placeholder>"
  },
  "sections": [
    {
      "number": "1",
      "title": "Title Page",
      "ich_e3_reference": "Section 1",
      "content_outline": "<what this section should contain>",
      "status": "DRAFT",
      "word_count_estimate": 0
    },
    {
      "number": "2",
      "title": "Synopsis",
      "ich_e3_reference": "Section 2",
      "content_outline": "Tabular summary of key study elements, populations, results",
      "status": "DRAFT",
      "word_count_estimate": 1000
    },
    {
      "number": "9",
      "title": "Introduction",
      "ich_e3_reference": "Section 9",
      "content_outline": "Disease background, unmet need, rationale, prior studies",
      "status": "DRAFT",
      "word_count_estimate": 1500
    },
    {
      "number": "10",
      "title": "Study Objectives",
      "ich_e3_reference": "Section 10",
      "content_outline": "Primary and secondary objectives and endpoints",
      "status": "DRAFT",
      "word_count_estimate": 500
    },
    {
      "number": "11",
      "title": "Investigational Plan",
      "ich_e3_reference": "Section 11",
      "content_outline": "Overall design, selection criteria, treatments, procedures",
      "status": "DRAFT",
      "word_count_estimate": 5000
    },
    {
      "number": "12",
      "title": "Study Patients",
      "ich_e3_reference": "Section 12",
      "content_outline": "Disposition, demographics, protocol deviations",
      "status": "DRAFT",
      "word_count_estimate": 2000
    },
    {
      "number": "13",
      "title": "Efficacy Evaluation",
      "ich_e3_reference": "Section 13",
      "content_outline": "Primary and secondary endpoint results, subgroup analyses",
      "status": "DRAFT",
      "word_count_estimate": 6000
    },
    {
      "number": "14",
      "title": "Safety Evaluation",
      "ich_e3_reference": "Section 14",
      "content_outline": "AE summary, deaths, SAEs, lab abnormalities, vital signs",
      "status": "DRAFT",
      "word_count_estimate": 5000
    },
    {
      "number": "15",
      "title": "Discussion and Overall Conclusions",
      "ich_e3_reference": "Section 15",
      "content_outline": "Integrated efficacy and safety discussion, benefit-risk",
      "status": "DRAFT",
      "word_count_estimate": 2000
    }
  ],
  "appendices": [
    "Protocol and amendments",
    "Investigators and study sites",
    "Patient data listings",
    "Statistical analysis plan",
    "Publications"
  ],
  "estimated_total_word_count": 25000,
  "regulatory_references": ["ICH E3", "FDA Module 5 Guidance", "EMA Clinical Study Reports Guideline"]
}"""


class CSRGenerator(BaseGenerator):
    ARTIFACT_TYPE = ArtifactType.CSR
    AGENT_NAME = "csr-generator"

    def _artifact_name(self, study_name: str) -> str:
        return f"{study_name} — Clinical Study Report v1.0 (Shell)"

    async def _build_content(
        self, job: GenerationJob, study: object, model_id: str
    ) -> dict:
        ctx = job.input_context or {}
        user_prompt = f"""Generate a Clinical Study Report (CSR) shell following ICH E3 structure for the following clinical trial.

Study details:
- Name: {study.name}
- Protocol Number: {study.protocol_number}
- Indication: {ctx.get("indication") or getattr(study, "indication", "Not specified")}
- Therapeutic Area: {ctx.get("therapeutic_area") or getattr(study, "therapeutic_area", "Not specified")}
- Phase: {ctx.get("phase") or getattr(study, "phase", "Not specified")}
- Sponsor: {ctx.get("sponsor") or getattr(study, "sponsor", "Not specified")}
- Primary Endpoint: {ctx.get("primary_endpoint", "Not specified")}
- Design: {ctx.get("design", "Randomized, double-blind, placebo-controlled")}
- Regulatory Regions: {ctx.get("regions", "FDA, EMA")}
- Key Results: {ctx.get("results_summary", "Study ongoing — results will be populated post-unblinding")}

Generate the complete ICH E3 section structure with detailed content outlines.
Return only valid JSON."""

        text = await self._call_claude(
            system_prompt=_SYSTEM,
            user_prompt=user_prompt,
            model_id=model_id,
            max_tokens=6000,
        )
        return self._parse_json_response(text)
