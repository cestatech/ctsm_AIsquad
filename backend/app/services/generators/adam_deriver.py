"""ADaM dataset derivation specification generator (SDTM → ADaM)."""

from __future__ import annotations

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob
from app.services.generators.base_generator import BaseGenerator

_SYSTEM = """You are a CDISC ADaM expert. You create ADaM dataset specifications following the CDISC ADaM Implementation Guide v1.3 and BDS structure.

Generate an ADaM derivation specification as a single JSON object. No prose outside the JSON.

Required schema:
{
  "document_type": "ADAM_SPECIFICATION",
  "version": "1.0",
  "adam_ig_version": "1.3",
  "datasets": [
    {
      "dataset": "ADSL",
      "label": "Subject Level Analysis Dataset",
      "structure": "One record per subject",
      "source_domains": ["DM", "DS", "EX"],
      "key_variables": ["STUDYID", "USUBJID"],
      "variables": [
        {
          "variable": "USUBJID",
          "label": "Unique Subject Identifier",
          "type": "Char",
          "origin": "SDTM.DM",
          "derivation": "DM.USUBJID",
          "controlled_terminology": null,
          "notes": ""
        }
      ],
      "population_flags": [
        {
          "variable": "ITTFL",
          "label": "Intent-to-Treat Population Flag",
          "derivation": "Y if randomised, N otherwise"
        }
      ]
    }
  ],
  "traceability_notes": ["<note>"],
  "regulatory_references": ["CDISC ADaM IG v1.3", "FDA ADaM Guidance", "PHUSE ADaM Scripts"]
}"""


class ADaMDerivationGenerator(BaseGenerator):
    ARTIFACT_TYPE = ArtifactType.ADAM_DATASET
    AGENT_NAME = "adam-derivation-generator"

    def _artifact_name(self, study_name: str) -> str:
        return f"{study_name} — ADaM Derivation Specification v1.0"

    async def _build_content(self, job: GenerationJob, study: object, model_id: str) -> dict:
        ctx = job.input_context or {}
        user_prompt = f"""Generate an ADaM derivation specification for the following clinical trial.

Study details:
- Name: {study.name}
- Protocol Number: {study.protocol_number}
- Indication: {ctx.get("indication") or getattr(study, "indication", "Not specified")}
- Phase: {ctx.get("phase") or getattr(study, "phase", "Not specified")}
- Primary Endpoint: {ctx.get("primary_endpoint", "Not specified")}
- Analysis Populations: {ctx.get("populations", "ITT, PP, Safety")}
- SDTM Domains Available: {ctx.get("sdtm_domains", "DM, DS, AE, CM, VS, LB, EX, MH")}

ADaM datasets to create:
{ctx.get("adam_datasets", "ADSL (subject-level), ADAE (adverse events), ADLB (labs), ADVS (vital signs), primary efficacy BDS dataset")}

Include full derivation algorithms, population flags, and analysis variable definitions.
Return only valid JSON."""

        text = await self._call_claude(system_prompt=_SYSTEM, user_prompt=user_prompt, model_id=model_id, max_tokens=6000)
        return self._parse_json_response(text)
