"""Tables, Listings, and Figures (TLF) specification generator."""

from __future__ import annotations

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob
from app.models.study import Study
from app.services.generators.base_generator import BaseGenerator

_SYSTEM = """You are a clinical reporting expert specialising in ICH E3 clinical study report structure and CDISC TLF standards.

Generate a TLF (Tables, Listings, Figures) specification as a single JSON object. No prose outside the JSON.
Use strict JSON: double-quoted strings only, escape internal quotes, no trailing commas.
The full document must fit in one response, so be selective rather than exhaustive:
at most 12 tables, 6 listings, and 5 figures covering the core ICH E3 displays, with
"row_definition", "column_definition", and "statistical_summary" under 200 characters each.

Required schema:
{
  "document_type": "TLF_SPECIFICATION",
  "version": "1.0",
  "ich_e3_sections": {
    "14.1": "Summary of Demographics and Baseline Characteristics",
    "14.2": "Summary of Treatment Compliance",
    "14.3": "Efficacy Tables",
    "14.4": "Safety Tables"
  },
  "tables": [
    {
      "id": "T-01",
      "title": "<title>",
      "section": "14.1",
      "population": "ITT",
      "source_dataset": "ADSL",
      "key_variables": [],
      "row_definition": "<row structure>",
      "column_definition": "<column structure>",
      "statistical_summary": "<mean (SD), n (%), etc.>",
      "footnotes": [],
      "program_name": "t_01_demog.sas"
    }
  ],
  "listings": [
    {
      "id": "L-01",
      "title": "<title>",
      "population": "Safety",
      "source_dataset": "",
      "sort_variables": [],
      "display_variables": [],
      "program_name": "l_01_ae_listing.sas"
    }
  ],
  "figures": [
    {
      "id": "F-01",
      "title": "<title>",
      "type": "line_plot",
      "source_dataset": "",
      "x_axis": "",
      "y_axis": "",
      "grouping": "",
      "program_name": "f_01_primary.sas"
    }
  ],
  "output_formats": ["RTF", "PDF"],
  "regulatory_references": ["ICH E3", "CDISC TLF Standards", "FDA Table and Figure Guidance 2022"]
}"""


class TLFAssembler(BaseGenerator):
    ARTIFACT_TYPE = ArtifactType.TLF
    AGENT_NAME = "tlf-assembler"

    def _artifact_name(self, study_name: str) -> str:
        return f"{study_name} — TLF Specification v1.0"

    async def _build_content(
        self, job: GenerationJob, study: Study, model_id: str
    ) -> dict:
        ctx = job.input_context or {}
        user_prompt = f"""Generate a complete TLF specification for the following clinical trial.

Study details:
- Name: {study.name}
- Protocol Number: {study.protocol_number}
- Indication: {ctx.get("indication") or getattr(study, "indication", "Not specified")}
- Phase: {ctx.get("phase") or getattr(study, "phase", "Not specified")}
- Primary Endpoint: {ctx.get("primary_endpoint", "Not specified")}
- Analysis Populations: {ctx.get("populations", "ITT, PP, Safety")}
- ADaM Datasets: {ctx.get("adam_datasets", "ADSL, ADAE, ADLB, ADVS, ADEFF")}
- Number of Treatment Arms: {ctx.get("treatment_arms", "2 (active vs placebo)")}

Generate the core tables, listings, and figures (at most 12 tables, 6 listings,
5 figures) covering:
1. Demographics and baseline (ICH E3 section 14.1)
2. Drug exposure and compliance (14.2)
3. Primary and secondary efficacy (14.3)
4. Safety: AEs, labs, vitals (14.4)
5. Key efficacy figures

Return only valid JSON."""

        text = await self._call_claude(
            system_prompt=_SYSTEM,
            user_prompt=user_prompt,
            model_id=model_id,
            max_tokens=16000,
        )
        return self._parse_json_response(text)
