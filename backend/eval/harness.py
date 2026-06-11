"""Run the model-comparison sweep and write reports.

Usage (from the backend/ directory, with the venv active):

    python -m eval.harness --config eval/models.example.yaml --out eval/results

What it does, for every (model × generator × fixture) cell:
  1. runs the generator's real prompt pipeline against the model,
  2. scores the output (JSON validity, schema coverage, CDISC conformance,
     placeholder rate, latency, tokens),
  3. writes the raw generated JSON to disk for human review.

It then writes three artifacts into the output directory:
  - results.csv          : one row per cell, every metric (machine-readable).
  - summary.md           : per-model aggregates + the CDISC-data vs authoring
                           split, i.e. the answer to "how small can we go".
  - review_template.csv  : one row per cell with blank columns for a reviewer to
                           record the *correction rate* — the human metric the
                           automated scores only approximate.

Concurrency is capped so a local single-GPU server is not overwhelmed.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from app.models.artifact import ArtifactType

from eval.fixtures import StudyFixture, get_fixtures
from eval.generators import (
    CDISC_DATA_TYPES,
    GENERATOR_CLASSES,
    GenerationOutcome,
    run_generator,
)
from eval.model_clients import ModelClient, build_client
from eval.scoring import ArtifactScore, score_artifact


@dataclass
class Cell:
    """One evaluated combination and its scores, flattened for reporting."""

    model_label: str
    model_tier: str
    artifact_type: str
    is_cdisc_data: bool
    fixture_key: str
    json_valid: bool
    first_attempt_valid: bool
    model_calls: int
    schema_coverage: float
    placeholder_rate: float
    cdisc_total: int
    cdisc_passed: int
    cdisc_failed: int
    cdisc_errors: int
    cdisc_pass_rate: float
    output_tokens: int | None
    latency_s: float
    transport_error: str | None
    parse_error: str | None


def _load_roster(config_path: Path, anthropic_api_key: str) -> list[ModelClient]:
    spec = yaml.safe_load(config_path.read_text())
    models = spec.get("models") if isinstance(spec, dict) else spec
    if not models:
        raise ValueError(f"no 'models' list found in {config_path}")
    clients: list[ModelClient] = []
    for entry in models:
        if entry.get("enabled", True) is False:
            continue
        clients.append(build_client(entry, anthropic_api_key=anthropic_api_key))
    if not clients:
        raise ValueError("roster has no enabled models")
    return clients


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in text).strip("-")


async def _run_cell(
    *,
    client: ModelClient,
    artifact_type: ArtifactType,
    fixture: StudyFixture,
    raw_dir: Path,
    sem: asyncio.Semaphore,
) -> Cell:
    async with sem:
        outcome: GenerationOutcome = await run_generator(
            artifact_type=artifact_type,
            client=client,
            study_fields=fixture.study_fields,
            input_context=fixture.input_context,
        )

    score: ArtifactScore = score_artifact(
        artifact_type=artifact_type,
        parsed=outcome.parsed,
        parse_error=outcome.parse_error,
    )

    # Persist the raw output (parsed JSON if we have it, else the last raw text)
    # so a human reviewer can read exactly what the model produced.
    stem = f"{_slug(client.label)}__{artifact_type.value}__{fixture.key}"
    if outcome.parsed is not None:
        (raw_dir / f"{stem}.json").write_text(json.dumps(outcome.parsed, indent=2))
    else:
        last = outcome.calls[-1].raw_text if outcome.calls else ""
        (raw_dir / f"{stem}.invalid.txt").write_text(last)

    return Cell(
        model_label=client.label,
        model_tier=client.tier,
        artifact_type=artifact_type.value,
        is_cdisc_data=artifact_type in CDISC_DATA_TYPES,
        fixture_key=fixture.key,
        json_valid=score.json_valid,
        first_attempt_valid=outcome.first_attempt_valid,
        model_calls=outcome.model_calls,
        schema_coverage=round(score.schema_coverage, 3),
        placeholder_rate=round(score.placeholder_rate, 3),
        cdisc_total=score.cdisc_total,
        cdisc_passed=score.cdisc_passed,
        cdisc_failed=score.cdisc_failed,
        cdisc_errors=score.cdisc_errors,
        cdisc_pass_rate=round(score.cdisc_pass_rate, 3),
        output_tokens=outcome.output_tokens,
        latency_s=round(outcome.total_latency_s, 2),
        transport_error=outcome.transport_error,
        parse_error=score.parse_error,
    )


def _write_results_csv(cells: list[Cell], path: Path) -> None:
    fieldnames = list(asdict(cells[0]).keys()) if cells else []
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for c in cells:
            writer.writerow(asdict(c))


def _write_review_template(cells: list[Cell], path: Path, raw_dir: Path) -> None:
    """Blank scoring sheet for the human metric the automation can't produce:
    the reviewer-correction rate (how much editing a draft needs to ship)."""
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "model_label",
                "artifact_type",
                "fixture_key",
                "raw_output_file",
                "json_valid",
                "cdisc_pass_rate",
                "placeholder_rate",
                # --- reviewer fills these in ---
                "fields_reviewed",
                "fields_corrected",
                "reviewer_correction_rate",  # fields_corrected / fields_reviewed
                "semantic_errors",  # clinically/statistically wrong but valid
                "acceptable_as_draft",  # y / n
                "reviewer_notes",
            ]
        )
        for c in cells:
            stem = f"{_slug(c.model_label)}__{c.artifact_type}__{c.fixture_key}"
            ext = "json" if c.json_valid else "invalid.txt"
            writer.writerow(
                [
                    c.model_label,
                    c.artifact_type,
                    c.fixture_key,
                    str((raw_dir / f"{stem}.{ext}").name),
                    c.json_valid,
                    c.cdisc_pass_rate,
                    c.placeholder_rate,
                    "", "", "", "", "", "",
                ]
            )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pct(values: list) -> str:
    """Percentage cell, or em dash when the group is empty (no data ≠ 0%)."""
    return f"{_mean([float(v) for v in values]):.0%}" if values else "—"


def _write_summary_md(cells: list[Cell], path: Path) -> None:
    models = sorted({c.model_label for c in cells})

    lines: list[str] = []
    lines.append("# Model comparison — Celerius generator eval\n")
    lines.append(
        "Automated metrics only. **Reviewer-correction rate is the deciding "
        "metric and must be filled in by a human** (see `review_template.csv`); "
        "the scores below approximate review burden but do not replace it.\n"
    )

    # Per-model overall.
    lines.append("## Overall, per model\n")
    lines.append(
        "| Model | Tier | Cells | JSON valid | 1st-try valid | "
        "Schema cov. | CDISC pass | Placeholder | Avg out-tok | Avg latency (s) |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in models:
        mc = [c for c in cells if c.model_label == m]
        tier = mc[0].model_tier
        toks = [c.output_tokens for c in mc if c.output_tokens is not None]
        lines.append(
            f"| {m} | {tier} | {len(mc)} "
            f"| {_pct([c.json_valid for c in mc])} "
            f"| {_pct([c.first_attempt_valid for c in mc])} "
            f"| {_pct([c.schema_coverage for c in mc])} "
            f"| {_pct([c.cdisc_pass_rate for c in mc])} "
            f"| {_pct([c.placeholder_rate for c in mc])} "
            f"| {int(_mean(toks)) if toks else '—'} "
            f"| {_mean([c.latency_s for c in mc]):.1f} |"
        )

    # The split that actually answers the question.
    lines.append("\n## CDISC data tier vs. authoring tier\n")
    lines.append(
        "The data tier (SDTM / ADaM / TLF) has a deterministic verification "
        "oracle and tightly-specified schemas, so a smaller model can fail "
        "safely there. The authoring tier (Protocol / SAP / ICF / CSR) has no "
        "oracle. Compare the two columns per model: a model that holds up on "
        "data but drops on authoring is a candidate for the routed setup "
        "(small local model for data, larger model for authoring).\n"
    )
    lines.append(
        "| Model | Data: JSON valid | Data: CDISC pass | "
        "Authoring: JSON valid | Authoring: schema cov. |"
    )
    lines.append("|---|---:|---:|---:|---:|")
    for m in models:
        data = [c for c in cells if c.model_label == m and c.is_cdisc_data]
        auth = [c for c in cells if c.model_label == m and not c.is_cdisc_data]
        lines.append(
            f"| {m} "
            f"| {_pct([c.json_valid for c in data])} "
            f"| {_pct([c.cdisc_pass_rate for c in data])} "
            f"| {_pct([c.json_valid for c in auth])} "
            f"| {_pct([c.schema_coverage for c in auth])} |"
        )

    # Per artifact type, so you can see which generators expose model weakness.
    lines.append("\n## Per artifact type (JSON valid %)\n")
    types = [t.value for t in GENERATOR_CLASSES]
    header = "| Model | " + " | ".join(types) + " |"
    lines.append(header)
    lines.append("|---" * (len(types) + 1) + "|")
    for m in models:
        row = [m]
        for t in types:
            tc = [c for c in cells if c.model_label == m and c.artifact_type == t]
            row.append(_pct([c.json_valid for c in tc]))
        lines.append("| " + " | ".join(row) + " |")

    # Surface transport errors so a dead endpoint isn't read as a bad model.
    errored = [c for c in cells if c.transport_error]
    if errored:
        lines.append("\n## ⚠ Transport / endpoint errors\n")
        lines.append(
            "These cells failed to reach the model — treat as missing data, not "
            "model quality:\n"
        )
        for c in errored:
            lines.append(
                f"- `{c.model_label}` / {c.artifact_type} / {c.fixture_key}: "
                f"{c.transport_error}"
            )

    path.write_text("\n".join(lines) + "\n")


async def _amain(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Celerius generator model eval")
    parser.add_argument(
        "--config", required=True, help="YAML roster (see models.example.yaml)"
    )
    parser.add_argument("--out", default="eval/results", help="output directory")
    parser.add_argument(
        "--fixtures",
        nargs="*",
        default=None,
        help="fixture keys to run (default: all)",
    )
    parser.add_argument(
        "--artifacts",
        nargs="*",
        default=None,
        help="artifact types to run, e.g. SDTM_DATASET PROTOCOL (default: all)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="max in-flight model calls (lower for a single local GPU)",
    )
    args = parser.parse_args(argv)

    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    out_dir = Path(args.out)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    clients = _load_roster(Path(args.config), anthropic_api_key)

    fixtures = get_fixtures(args.fixtures)
    if args.artifacts:
        wanted = {a.upper() for a in args.artifacts}
        artifact_types = [t for t in GENERATOR_CLASSES if t.value in wanted]
        unknown = wanted - {t.value for t in artifact_types}
        if unknown:
            print(f"error: unknown artifact type(s): {sorted(unknown)}", file=sys.stderr)
            return 2
    else:
        artifact_types = list(GENERATOR_CLASSES.keys())

    total = len(clients) * len(artifact_types) * len(fixtures)
    print(
        f"Running {total} cells: {len(clients)} models × "
        f"{len(artifact_types)} artifacts × {len(fixtures)} fixtures",
        file=sys.stderr,
    )

    sem = asyncio.Semaphore(args.concurrency)
    tasks = [
        _run_cell(
            client=client,
            artifact_type=artifact_type,
            fixture=fixture,
            raw_dir=raw_dir,
            sem=sem,
        )
        for client in clients
        for artifact_type in artifact_types
        for fixture in fixtures
    ]

    cells: list[Cell] = []
    done = 0
    for coro in asyncio.as_completed(tasks):
        cell = await coro
        cells.append(cell)
        done += 1
        flag = "ok" if cell.json_valid else ("ERR" if cell.transport_error else "INVALID")
        print(
            f"  [{done}/{total}] {cell.model_label} / {cell.artifact_type} / "
            f"{cell.fixture_key} -> {flag}",
            file=sys.stderr,
        )

    for client in clients:
        await client.aclose()

    # Stable ordering for readable CSVs.
    cells.sort(key=lambda c: (c.model_label, c.artifact_type, c.fixture_key))

    _write_results_csv(cells, out_dir / "results.csv")
    _write_summary_md(cells, out_dir / "summary.md")
    _write_review_template(cells, out_dir / "review_template.csv", raw_dir)

    print(
        f"\nWrote:\n  {out_dir/'results.csv'}\n  {out_dir/'summary.md'}\n"
        f"  {out_dir/'review_template.csv'}\n  {raw_dir}/ (raw outputs)",
        file=sys.stderr,
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_amain(sys.argv[1:])))


if __name__ == "__main__":
    main()
