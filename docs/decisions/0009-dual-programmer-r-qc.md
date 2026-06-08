# ADR-0009: Dual-Programmer R QC for Data Pipeline Steps

**Date:** 2026-06-05
**Status:** Accepted

## Context

Industry statistical programming practice requires independent QC: a primary programmer and a QC programmer each produce code from the same specification without seeing the other's program, then outputs are compared.

Phases 4–6 (Raw→SDTM→ADaM→TLF) previously produced JSON artifacts only, with no executable R programs or output reconciliation.

## Decision

Every data transformation step (`RAW_TO_SDTM`, `SDTM_TO_ADAM`, `ADAM_TO_TLF`) runs **dual-programmer R QC** automatically on artifact generation:

1. **Primary programmer agent** (`stat-primary-programmer`) — `AIDecision` + R program
2. **QC programmer agent** (`stat-qc-programmer`) — independent `AIDecision` + R program (primary code never disclosed)
3. **Execution** — both programs run via `Rscript` when available
4. **Comparison** — output CSV hashes compared; status `MATCH`, `MISMATCH`, `EXECUTION_FAILED`, or `R_UNAVAILABLE`
5. **Persistence** — append-only `statistical_program_qc_runs` table; both programs stored immutably

When R is not installed (typical Docker dev), programs are still generated and stored with status `R_UNAVAILABLE` for manual QC.

## Consequences

- Regulatory-aligned QC workflow for statistical programming
- Two additional AI decisions per pipeline step (cost/latency)
- R optional in dev; production should include R in the execution environment
- TLF generation wired with same QC pattern
