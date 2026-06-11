"""Adapters that run the real generator prompts against an arbitrary model.

The platform's generators (``SDTMMappingGenerator``, ``ProtocolGenerator``, …)
encapsulate the exact system prompt, user-prompt construction, and JSON parsing
used in production. We want the eval to exercise *those* — not a copy that can
drift — so this module instantiates each generator without its database-bound
``__init__`` and monkeypatches the single method that reaches the network,
``_call_claude``. Everything else (prompt assembly, ``_format_brief_for_prompt``,
``_parse_json_response`` including the SAP repair retry) runs unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from app.models.artifact import ArtifactType
from app.services.generators.adam_deriver import ADaMDerivationGenerator
from app.services.generators.base_generator import BaseGenerator
from app.services.generators.csr_generator import CSRGenerator
from app.services.generators.icf_generator import ICFGenerator
from app.services.generators.protocol_generator import ProtocolGenerator
from app.services.generators.sap_generator import SAPGenerator
from app.services.generators.sdtm_mapper import SDTMMappingGenerator
from app.services.generators.tlf_assembler import TLFAssembler

from eval.model_clients import CompletionResult, ModelClient

# Generators that follow the prompt → _call_claude → _parse_json_response shape.
# Keyed by the ArtifactType they emit, which is also the key the CDISC validation
# engine uses to pick a rule set.
GENERATOR_CLASSES: dict[ArtifactType, type[BaseGenerator]] = {
    ArtifactType.SDTM_DATASET: SDTMMappingGenerator,
    ArtifactType.ADAM_DATASET: ADaMDerivationGenerator,
    ArtifactType.TLF: TLFAssembler,
    ArtifactType.PROTOCOL: ProtocolGenerator,
    ArtifactType.SAP: SAPGenerator,
    ArtifactType.ICF: ICFGenerator,
    ArtifactType.CSR: CSRGenerator,
}

# The CDISC data tier — where a deterministic verification oracle exists and a
# smaller model can fail safely. Reports group on this to answer the actual
# question (how small can the *data* pipeline go vs. the authoring documents).
CDISC_DATA_TYPES = {ArtifactType.SDTM_DATASET, ArtifactType.ADAM_DATASET, ArtifactType.TLF}


@dataclass
class CallRecord:
    """Telemetry for one underlying model call (a generation may make several —
    e.g. the SAP generator retries once to repair invalid JSON)."""

    latency_s: float
    input_tokens: int | None
    output_tokens: int | None
    error: str | None
    raw_text: str


@dataclass
class GenerationOutcome:
    """Result of running one generator against one model on one fixture."""

    parsed: dict | None
    parse_error: str | None
    calls: list[CallRecord] = field(default_factory=list)

    @property
    def model_calls(self) -> int:
        return len(self.calls)

    @property
    def first_attempt_valid(self) -> bool:
        # The generation returned a dict and did so without a repair retry.
        return self.parsed is not None and self.model_calls == 1

    @property
    def json_valid(self) -> bool:
        return self.parsed is not None

    @property
    def total_latency_s(self) -> float:
        return sum(c.latency_s for c in self.calls)

    @property
    def output_tokens(self) -> int | None:
        vals = [c.output_tokens for c in self.calls if c.output_tokens is not None]
        return sum(vals) if vals else None

    @property
    def transport_error(self) -> str | None:
        errs = [c.error for c in self.calls if c.error]
        return "; ".join(errs) if errs else None


def _make_job(input_context: dict[str, Any]) -> SimpleNamespace:
    """A stand-in for GenerationJob. The prompt builders only read input_context."""
    return SimpleNamespace(input_context=input_context)


def _make_study(study_fields: dict[str, Any]) -> SimpleNamespace:
    """A stand-in for the Study ORM object. Prompts read name / protocol_number /
    indication / therapeutic_area / phase / sponsor."""
    return SimpleNamespace(**study_fields)


async def run_generator(
    *,
    artifact_type: ArtifactType,
    client: ModelClient,
    study_fields: dict[str, Any],
    input_context: dict[str, Any],
) -> GenerationOutcome:
    """Run one generator's real prompt pipeline against ``client``.

    The model id passed down to the generator is ignored by our patched
    ``_call_claude`` (the client already targets a specific model), but we still
    thread a value through so the prompt-building code paths behave identically.
    """
    gen_cls = GENERATOR_CLASSES[artifact_type]

    # Build the generator without its DB-bound __init__.
    gen = object.__new__(gen_cls)

    calls: list[CallRecord] = []

    async def patched_call_claude(
        *,
        system_prompt: str,
        user_prompt: str,
        model_id: str,
        max_tokens: int = 4096,
    ) -> str:
        result: CompletionResult = await client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )
        calls.append(
            CallRecord(
                latency_s=result.latency_s,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                error=result.error,
                raw_text=result.text,
            )
        )
        # Return the raw text so the generator's own parser/repair logic runs.
        return result.text

    # Instance attribute shadows the bound method; called as self._call_claude(...)
    # it receives no `self`, matching patched_call_claude's keyword-only signature.
    gen._call_claude = patched_call_claude  # type: ignore[method-assign]

    job = _make_job(input_context)
    study = _make_study(study_fields)

    try:
        parsed = await gen._build_content(job=job, study=study, model_id="eval-model")
        return GenerationOutcome(parsed=parsed, parse_error=None, calls=calls)
    except ValueError as exc:
        # _parse_json_response raises ValueError when no valid JSON can be salvaged.
        return GenerationOutcome(parsed=None, parse_error=str(exc), calls=calls)
    except Exception as exc:  # noqa: BLE001 — record, don't crash the sweep
        return GenerationOutcome(
            parsed=None,
            parse_error=f"{type(exc).__name__}: {exc}",
            calls=calls,
        )
