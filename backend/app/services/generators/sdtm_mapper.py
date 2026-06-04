"""SDTM variable mapping generator (eCRF → SDTM)."""

from __future__ import annotations

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob
from app.services.generators.base_generator import BaseGenerator

_SYSTEM = """You are a CDISC SDTM expert. You map eCRF fields to SDTM variables following CDISC SDTM Implementation Guide v3.3 and CDISC Foundational Standards.

Generate an SDTM mapping specification as a single JSON object. No prose outside the JSON.

Required schema:
{
  "document_type": "SDTM_MAPPING",
  "version": "1.0",
  "sdtm_ig_version": "3.3",
  "domains": [
    {
      "domain": "DM",
      "domain_label": "Demographics",
      "class": "Special-Purpose",
      "variables": [
        {
          "variable": "USUBJID",
          "label": "Unique Subject Identifier",
          "type": "Char",
          "controlled_terminology": null,
          "origin": "Assigned",
          "source_field": null,
          "transformation": "CONCAT(STUDYID, '-', SITEID, '-', SUBJID)",
          "notes": ""
        }
      ]
    }
  ],
  "supplemental_qualifiers": [],
  "define_xml_version": "2.1",
  "validation_notes": ["<note>"],
  "regulatory_references": ["CDISC SDTM IG v3.3", "FDA Data Standards Catalog", "PMDA Data Standards"]
}"""


class SDTMMappingGenerator(BaseGenerator):
    ARTIFACT_TYPE = ArtifactType.SDTM_DATASET
    AGENT_NAME = "sdtm-mapping-generator"

    def _artifact_name(self, study_name: str) -> str:
        return f"{study_name} — SDTM Mapping Specification v1.0"

    async def _build_content(self, job: GenerationJob, study: object, model_id: str) -> dict:
        ctx = job.input_context or {}
        ecrf_fields = ctx.get("ecrf_fields", [])
        user_prompt = f"""Generate an SDTM mapping specification for the following clinical trial.

Study details:
- Name: {study.name}
- Protocol Number: {study.protocol_number}
- Indication: {ctx.get("indication") or getattr(study, "indication", "Not specified")}
- Phase: {ctx.get("phase") or getattr(study, "phase", "Not specified")}
- Therapeutic Area: {ctx.get("therapeutic_area") or getattr(study, "therapeutic_area", "Not specified")}

eCRF fields to map (if provided):
{ecrf_fields if ecrf_fields else "Standard Phase " + str(getattr(study, "phase", "II/III")) + " fields: demographics, disposition, adverse events, concomitant medications, vital signs, labs, efficacy assessments"}

CDISC domains to include:
{ctx.get("domains", "DM, DS, AE, CM, VS, LB, EX, MH, EC, IE — include all relevant domains")}

Generate complete variable-level mappings for each domain including transformation logic.
Return only valid JSON."""

        text = await self._call_claude(system_prompt=_SYSTEM, user_prompt=user_prompt, model_id=model_id, max_tokens=6000)
        return self._parse_json_response(text)
