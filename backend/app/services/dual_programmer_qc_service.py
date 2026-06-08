"""Dual-programmer R QC — primary and independent QC statistical programmers."""

from __future__ import annotations

import hashlib
import json
import re
from uuid import UUID

import anthropic
from anthropic.types import TextBlock
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.audit import AuditAction
from app.models.statistical_qc import (
    StatisticalProgramQCRun,
    StatisticalQCStatus,
    StatisticalQCWorkflow,
)
from app.models.user import User
from app.repositories.statistical_qc_repository import StatisticalQCRepository
from app.services.audit_service import AuditService
from app.services.intelligence_service import AIDecisionService
from app.services.r_program_runner import run_dual_program_comparison

_MODEL_ID = "claude-sonnet-4-20250514"
_PRIMARY_AGENT = "stat-primary-programmer"
_QC_AGENT = "stat-qc-programmer"

_WORKFLOW_PROMPTS: dict[StatisticalQCWorkflow, dict[str, str]] = {
    StatisticalQCWorkflow.RAW_TO_SDTM: {
        "task": "Derive SDTM domains from raw CSV input files in INPUT_DIR",
        "outputs": "Write one CSV per SDTM domain to OUTPUT_DIR (e.g. dm.csv)",
        "primary_role": (
            "You are the primary statistical programmer for a clinical trial. "
            "Write complete, runnable R code using base R and read.csv/write.csv."
        ),
        "qc_role": (
            "You are an independent QC statistical programmer. You have NOT seen "
            "the primary programmer's code. Write your own independent R program "
            "from the same input specification to produce equivalent SDTM outputs."
        ),
    },
    StatisticalQCWorkflow.SDTM_TO_ADAM: {
        "task": "Derive ADaM analysis datasets (ADSL required) from SDTM CSVs in INPUT_DIR",
        "outputs": "Write ADaM CSVs to OUTPUT_DIR (at minimum adsl.csv)",
        "primary_role": (
            "You are the primary statistical programmer deriving ADaM from SDTM."
        ),
        "qc_role": (
            "You are an independent QC statistical programmer. Write independent R "
            "code to derive the same ADaM datasets without seeing primary code."
        ),
    },
    StatisticalQCWorkflow.ADAM_TO_TLF: {
        "task": "Produce TLF summary table outputs from ADaM CSVs in INPUT_DIR",
        "outputs": "Write summary table CSVs to OUTPUT_DIR (e.g. t_demog.csv)",
        "primary_role": (
            "You are the primary statistical programmer creating TLF table outputs."
        ),
        "qc_role": (
            "You are an independent QC statistical programmer. Write independent R "
            "code to produce equivalent TLF summary tables."
        ),
    },
}

def _primary_sdtm_template() -> str:
    return """# Primary programmer — Raw to SDTM (deterministic template)
`%||%` <- function(a, b) if (!is.null(a)) a else b
dm_path <- file.path(INPUT_DIR, "dm.csv")
if (file.exists(dm_path)) {
  raw <- read.csv(dm_path, stringsAsFactors = FALSE)
  sdtm <- data.frame(
    STUDYID = raw$STUDYID %||% raw$studyid %||% "STUDY",
    DOMAIN = "DM",
    USUBJID = raw$USUBJID %||% raw$subject_id %||% raw$SUBJECT_ID,
    stringsAsFactors = FALSE
  )
  if ("AGE" %in% names(raw) || "age" %in% names(raw)) {
    sdtm$AGE <- raw$AGE %||% raw$age
  }
  write.csv(sdtm, file.path(OUTPUT_DIR, "dm.csv"), row.names = FALSE)
}
"""


def _qc_sdtm_template() -> str:
    return """# QC programmer — Raw to SDTM (independent template)
`%||%` <- function(a, b) if (!is.null(a)) a else b
dm_path <- file.path(INPUT_DIR, "dm.csv")
if (file.exists(dm_path)) {
  dat <- read.csv(dm_path, stringsAsFactors = FALSE)
  out <- data.frame(
    STUDYID = if ("STUDYID" %in% names(dat)) dat$STUDYID else "STUDY",
    DOMAIN = rep("DM", nrow(dat)),
    USUBJID = if ("USUBJID" %in% names(dat)) dat$USUBJID else dat[[1]],
    stringsAsFactors = FALSE
  )
  if ("age" %in% tolower(names(dat))) {
    age_col <- names(dat)[tolower(names(dat)) == "age"][1]
    out$AGE <- dat[[age_col]]
  } else if ("AGE" %in% names(dat)) {
    out$AGE <- dat$AGE
  }
  write.csv(out, file.path(OUTPUT_DIR, "dm.csv"), row.names = FALSE)
}
"""


def _primary_adam_template() -> str:
    return """# Primary programmer — SDTM to ADSL
`%||%` <- function(a, b) if (!is.null(a)) a else b
dm_path <- file.path(INPUT_DIR, "dm.csv")
if (file.exists(dm_path)) {
  dm <- read.csv(dm_path, stringsAsFactors = FALSE)
  adsl <- data.frame(
    STUDYID = dm$STUDYID,
    USUBJID = dm$USUBJID,
    SUBJID = sub(".*-", "", dm$USUBJID),
    ITTFL = "Y",
    SAFFL = "Y",
    stringsAsFactors = FALSE
  )
  if ("AGE" %in% names(dm)) adsl$AGE <- dm$AGE
  write.csv(adsl, file.path(OUTPUT_DIR, "adsl.csv"), row.names = FALSE)
}
"""


def _qc_adam_template() -> str:
    return """# QC programmer — SDTM to ADSL (independent)
dm_path <- file.path(INPUT_DIR, "dm.csv")
if (file.exists(dm_path)) {
  sdtm_dm <- read.csv(dm_path, stringsAsFactors = FALSE)
  adsl_qc <- data.frame(
    STUDYID = sdtm_dm$STUDYID,
    USUBJID = sdtm_dm$USUBJID,
    SUBJID = gsub("^[^-]+-", "", sdtm_dm$USUBJID),
    ITTFL = rep("Y", nrow(sdtm_dm)),
    SAFFL = rep("Y", nrow(sdtm_dm)),
    stringsAsFactors = FALSE
  )
  if ("AGE" %in% colnames(sdtm_dm)) adsl_qc$AGE <- sdtm_dm$AGE
  write.csv(adsl_qc, file.path(OUTPUT_DIR, "adsl.csv"), row.names = FALSE)
}
"""


def _primary_tlf_template() -> str:
    return """# Primary programmer — ADaM to TLF demog table
adsl_path <- file.path(INPUT_DIR, "adsl.csv")
if (file.exists(adsl_path)) {
  adsl <- read.csv(adsl_path, stringsAsFactors = FALSE)
  if ("AGE" %in% names(adsl)) {
    summary_row <- data.frame(
      statistic = "Mean Age (SD)",
      value = sprintf("%.1f", mean(as.numeric(adsl$AGE), na.rm = TRUE)),
      n = nrow(adsl),
      stringsAsFactors = FALSE
    )
  } else {
    summary_row <- data.frame(
      statistic = "Subjects",
      value = as.character(nrow(adsl)),
      n = nrow(adsl),
      stringsAsFactors = FALSE
    )
  }
  write.csv(summary_row, file.path(OUTPUT_DIR, "t_demog.csv"), row.names = FALSE)
}
"""


def _qc_tlf_template() -> str:
    return """# QC programmer — ADaM to TLF demog table (independent)
adsl_path <- file.path(INPUT_DIR, "adsl.csv")
if (file.exists(adsl_path)) {
  d <- read.csv(adsl_path, stringsAsFactors = FALSE)
  n <- nrow(d)
  if ("AGE" %in% names(d)) {
    m <- mean(as.numeric(d$AGE), na.rm = TRUE)
    row <- data.frame(statistic = "Mean Age (SD)", value = format(round(m, 1), nsmall = 1), n = n)
  } else {
    row <- data.frame(statistic = "Subjects", value = as.character(n), n = n)
  }
  write.csv(row, file.path(OUTPUT_DIR, "t_demog.csv"), row.names = FALSE)
}
"""


def _r_templates() -> dict[StatisticalQCWorkflow, tuple[str, str]]:
    return {
        StatisticalQCWorkflow.RAW_TO_SDTM: (
            _primary_sdtm_template(),
            _qc_sdtm_template(),
        ),
        StatisticalQCWorkflow.SDTM_TO_ADAM: (
            _primary_adam_template(),
            _qc_adam_template(),
        ),
        StatisticalQCWorkflow.ADAM_TO_TLF: (
            _primary_tlf_template(),
            _qc_tlf_template(),
        ),
    }


class DualProgrammerQCService:
    """Generate, execute, and compare primary vs QC R programs."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = StatisticalQCRepository(db)
        self._ai = AIDecisionService(db)
        self._audit = AuditService(db)
        settings = get_settings()
        self._client = (
            anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            if settings.ANTHROPIC_API_KEY
            else None
        )

    async def run_qc(
        self,
        *,
        workflow_step: StatisticalQCWorkflow,
        study_id: UUID,
        actor: User,
        input_payload: dict,
        output_artifact_id: UUID | None = None,
        source_artifact_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> StatisticalProgramQCRun:
        """
        Run full dual-programmer QC: two AI decisions, two R programs, compare.
        """
        prompts = _WORKFLOW_PROMPTS[workflow_step]

        primary_decision = await self._ai.begin_decision(
            organization_id=actor.organization_id,
            agent_name=_PRIMARY_AGENT,
            decision_type=f"STAT_PROG_PRIMARY_{workflow_step.value}",
            study_id=study_id,
            model_id=_MODEL_ID,
            input_context={
                "workflow": workflow_step.value,
                "role": "primary_programmer",
            },
        )

        primary_program = await self._generate_program(
            role_prompt=prompts["primary_role"],
            task=prompts["task"],
            outputs=prompts["outputs"],
            input_payload=input_payload,
            workflow_step=workflow_step,
            variant="primary",
        )

        await self._ai.complete_decision(
            decision=primary_decision,
            output={"r_program_lines": primary_program.count("\n") + 1},
            reasoning="Primary statistical programmer R program generated",
            confidence=0.8,
        )

        qc_decision = await self._ai.begin_decision(
            organization_id=actor.organization_id,
            agent_name=_QC_AGENT,
            decision_type=f"STAT_PROG_QC_{workflow_step.value}",
            study_id=study_id,
            model_id=_MODEL_ID,
            input_context={
                "workflow": workflow_step.value,
                "role": "qc_programmer",
                "note": "Independent — primary program not disclosed",
            },
        )

        qc_program = await self._generate_program(
            role_prompt=prompts["qc_role"],
            task=prompts["task"],
            outputs=prompts["outputs"],
            input_payload=input_payload,
            workflow_step=workflow_step,
            variant="qc",
        )

        await self._ai.complete_decision(
            decision=qc_decision,
            output={"r_program_lines": qc_program.count("\n") + 1},
            reasoning="Independent QC statistical programmer R program generated",
            confidence=0.8,
        )

        comparison = run_dual_program_comparison(
            primary_program=primary_program,
            qc_program=qc_program,
            input_payload=input_payload,
        )

        status = _map_comparison_status(comparison)

        run = StatisticalProgramQCRun(
            organization_id=actor.organization_id,
            study_id=study_id,
            workflow_step=workflow_step,
            status=status,
            source_artifact_id=source_artifact_id,
            output_artifact_id=output_artifact_id,
            primary_ai_decision_id=primary_decision.id,
            qc_ai_decision_id=qc_decision.id,
            primary_r_program=primary_program,
            qc_r_program=qc_program,
            primary_program_hash=_hash_text(primary_program),
            qc_program_hash=_hash_text(qc_program),
            comparison_result=comparison,
            created_by_id=actor.id,
        )
        await self._repo.create(run)

        await self._audit.log(
            action=AuditAction.AI_GENERATION_COMPLETED,
            resource_type="statistical_program_qc",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=run.id,
            after_state={
                "workflow_step": workflow_step.value,
                "status": status.value,
                "output_artifact_id": str(output_artifact_id) if output_artifact_id else None,
                "comparison_status": comparison.get("status"),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return run

    async def _generate_program(
        self,
        *,
        role_prompt: str,
        task: str,
        outputs: str,
        input_payload: dict,
        workflow_step: StatisticalQCWorkflow,
        variant: str,
    ) -> str:
        if self._client:
            return await self._call_claude_for_r(
                role_prompt=role_prompt,
                task=task,
                outputs=outputs,
                input_payload=input_payload,
            )
        primary_tpl, qc_tpl = _r_templates()[workflow_step]
        return primary_tpl if variant == "primary" else qc_tpl

    async def _call_claude_for_r(
        self,
        *,
        role_prompt: str,
        task: str,
        outputs: str,
        input_payload: dict,
    ) -> str:
        user_prompt = f"""{role_prompt}

Task: {task}
Required outputs: {outputs}

Input specification (JSON in INPUT_DIR/input_spec.json):
{json.dumps(input_payload, indent=2, default=str)[:8000]}

Requirements:
- Use INPUT_DIR and OUTPUT_DIR environment variables (already set)
- Use only base R (no packages unless essential)
- Write complete runnable R code only — no markdown fences
- Read input CSVs from INPUT_DIR
- Write output CSVs to OUTPUT_DIR
"""

        response = await self._client.messages.create(
            model=_MODEL_ID,
            max_tokens=4000,
            system="You output only runnable R code for clinical data programming.",
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = ""
        for block in response.content:
            if isinstance(block, TextBlock):
                text += block.text
        return _strip_fences(text)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _strip_fences(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:r|R)?\s*([\s\S]*?)```", text)
    if fence:
        return fence.group(1).strip()
    return text


def _map_comparison_status(comparison: dict) -> StatisticalQCStatus:
    raw = comparison.get("status", "PROGRAMS_GENERATED")
    mapping = {
        "MATCH": StatisticalQCStatus.MATCH,
        "MISMATCH": StatisticalQCStatus.MISMATCH,
        "EXECUTION_FAILED": StatisticalQCStatus.EXECUTION_FAILED,
        "R_UNAVAILABLE": StatisticalQCStatus.R_UNAVAILABLE,
    }
    return mapping.get(raw, StatisticalQCStatus.PROGRAMS_GENERATED)
