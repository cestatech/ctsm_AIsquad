"""Clinical Study Report (CSR) generator."""

from __future__ import annotations

import json

import anthropic
from anthropic.types import TextBlock

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob
from app.models.study import Study
from app.services.generators.base_generator import BaseGenerator

_PROSE_SYSTEM = """You are a senior medical writer drafting ICH E3 Clinical Study Report prose.

Write regulatory-ready narrative paragraphs for the requested CSR section only.
- Use complete sentences and professional medical writing tone
- Reference TLF tables by ID when provided
- Do not invent patient-level results not supported by the context
- Return plain text prose only (no JSON, no markdown headings)
"""

_DEFAULT_MODEL = "claude-sonnet-4-20250514"

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
        self, job: GenerationJob, study: Study, model_id: str
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
            max_tokens=16000,
        )
        return self._parse_json_response(text)

    @staticmethod
    async def generate_section_prose(
        section_id: str,
        context: dict,
        *,
        api_key: str | None = None,
        model_id: str = _DEFAULT_MODEL,
    ) -> str:
        """Generate full ICH E3 prose for one CSR section."""
        if not api_key:
            return CSRGenerator._deterministic_section_prose(section_id, context)

        title = context.get("section_title", f"Section {section_id}")
        user_prompt = f"""Draft ICH E3 CSR Section {section_id}: {title}

Context:
{json.dumps(context, indent=2, default=str)}

Write 2–5 paragraphs of submission-ready prose for this section."""

        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=model_id,
            max_tokens=4000,
            system=_PROSE_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = ""
        for block in response.content:
            if isinstance(block, TextBlock):
                text += block.text
        prose = text.strip()
        return prose or CSRGenerator._deterministic_section_prose(section_id, context)

    @staticmethod
    def _deterministic_section_prose(section_id: str, context: dict) -> str:
        """Template prose when AI is unavailable."""
        title = context.get("section_title", f"Section {section_id}")
        study_name = context.get("study_name", "the study")
        protocol = context.get("protocol_number", "the protocol")
        tables = context.get("tlf_tables") or []
        table_refs = ", ".join(
            f"{t.get('table_id') or t.get('id')}: {t.get('title', 'TLF output')}"
            for t in tables[:4]
        ) or "available TLF outputs"

        protocol_excerpt = context.get("protocol_excerpt") or {}
        sap_excerpt = context.get("sap_excerpt") or {}
        primary_endpoint = (
            sap_excerpt.get("primary_endpoint")
            or protocol_excerpt.get("primary_endpoint")
            or "the prespecified primary endpoint"
        )
        objectives = protocol_excerpt.get("objectives_primary") or []
        objective_text = (
            "; ".join(objectives) if objectives else "the study objectives defined in the protocol"
        )
        instructions = context.get("instructions")
        instruction_note = (
            f" Additional author guidance: {instructions}" if instructions else ""
        )

        templates: dict[str, str] = {
            "1": (
                f"This clinical study report presents results for {study_name} "
                f"(protocol {protocol}). The report follows ICH E3 structure and "
                f"integrates programmed TLF outputs referenced throughout the document."
            ),
            "2": (
                f"The synopsis summarizes the design, population, and key findings for "
                f"{study_name}. Objectives included {objective_text}. Efficacy and safety "
                f"results are integrated from TLF tables {table_refs}."
            ),
            "9": (
                f"Section 9 introduces the clinical background and rationale for {study_name}. "
                f"The investigational program was conducted under protocol {protocol} to "
                f"address the objectives described in the approved protocol and SAP."
            ),
            "10": (
                f"The study objectives were {objective_text}. The primary endpoint was "
                f"{primary_endpoint}, with supporting secondary endpoints and estimands "
                f"defined in the SAP."
            ),
            "11": (
                f"The investigational plan for {study_name} followed the approved protocol "
                f"design ({protocol_excerpt.get('design_summary') or 'randomized controlled design'}). "
                f"Procedures, visit schedules, and analysis populations were executed per the SAP."
            ),
            "12": (
                f"Study patients are summarized using disposition and demographic TLF tables "
                f"({table_refs}). Subject accountability and baseline characteristics are "
                f"presented in accordance with ICH E3 expectations for Section 12."
            ),
            "13": (
                f"Efficacy results for the primary endpoint ({primary_endpoint}) are presented "
                f"in Section 13 using TLF evidence ({table_refs}). Estimand definitions and "
                f"statistical methods followed the SAP."
            ),
            "14": (
                f"Safety evaluation integrates adverse events, laboratory, and vital sign findings "
                f"from TLF tables ({table_refs}) together with SDTM/ADaM traceability. Exposure "
                f"and treatment-emergent events are summarized for the analysis populations."
            ),
            "15": (
                f"The overall discussion integrates efficacy findings related to {primary_endpoint} "
                f"with the safety profile observed in {study_name}. Benefit-risk conclusions "
                f"should be finalized by the medical writer prior to regulatory submission."
            ),
        }

        base = templates.get(
            section_id,
            (
                f"This section ({title}) for {study_name} is drafted from protocol {protocol} "
                f"and TLF outputs ({table_refs}) pending medical writer review."
            ),
        )
        if context.get("narrative_summary"):
            base = f"{base} {context['narrative_summary']}"
        return f"{base}{instruction_note}"
