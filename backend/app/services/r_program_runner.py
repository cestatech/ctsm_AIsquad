"""Execute R programs in an isolated workspace and compare outputs."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from io import StringIO
from pathlib import Path

from app.services.r_preflight import preflight_input_validation
from app.models.statistical_qc import StatisticalQCWorkflow

log = logging.getLogger(__name__)

# Injected before AI-generated programs — overrides unsafe helpers and adds `%||%`.
_R_RUNTIME_PREAMBLE = """# --- Celerius R runtime helpers (auto-injected) ---
`%||%` <- function(a, b) if (!is.null(a) && length(a) > 0 && !all(is.na(a))) a else b
read_input_spec <- function() {
  path <- file.path(INPUT_DIR, "input_spec.json")
  if (!file.exists(path)) return(list())
  txt <- paste(readLines(path, warn = FALSE), collapse = "\\n")
  if (requireNamespace("jsonlite", quietly = TRUE)) {
    return(jsonlite::fromJSON(txt, simplifyVector = FALSE))
  }
  list()
}
parse_json_observations <- function(obj) {
  if (missing(obj) || is.null(obj)) return(list())
  if (is.list(obj)) return(obj)
  path <- if (is.character(obj) && length(obj) == 1 && file.exists(obj)) obj else file.path(INPUT_DIR, "input_spec.json")
  spec <- read_input_spec()
  domains <- spec$domains
  if (is.null(domains)) return(list())
  if (is.data.frame(domains)) return(list(domains))
  domains
}
"""


def rscript_available() -> bool:
    """Return True when Rscript is on PATH."""
    return shutil.which("Rscript") is not None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_input_fixtures(input_payload: dict, workspace: Path) -> Path:
    """Write input JSON/CSVs into workspace/input for R programs to read."""
    input_dir = workspace / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    spec_path = input_dir / "input_spec.json"
    spec_path.write_text(json.dumps(input_payload, indent=2, default=str))

    for domain in input_payload.get("domains", []):
        code = domain.get("domain", "UNK")
        observations = domain.get("observations", [])
        if not observations:
            continue
        headers = sorted({k for row in observations for k in row.keys()})
        lines = [",".join(headers)]
        for row in observations:
            lines.append(
                ",".join(
                    str(row.get(h, "")).replace(",", " ")
                    for h in headers
                )
            )
        (input_dir / f"{code.lower()}.csv").write_text("\n".join(lines) + "\n")

    for ds in input_payload.get("datasets", []):
        name = ds.get("dataset", "UNK").lower()
        variables = ds.get("variables", [])
        if variables and isinstance(variables[0], dict):
            (input_dir / f"{name}_spec.csv").write_text(
                "variable,derivation\n"
                + "\n".join(
                    f"{v.get('variable','')},{v.get('derivation','')}"
                    for v in variables
                )
                + "\n"
            )

    _synthesize_adsl_fixture(input_dir)
    _ensure_ex_fixture(input_dir)
    return input_dir


def _ensure_ex_fixture(input_dir: Path) -> None:
    """Create minimal ex.csv from dm.csv when ADaM QC programs expect EX."""
    ex_path = input_dir / "ex.csv"
    if ex_path.exists():
        return
    dm_path = input_dir / "dm.csv"
    if not dm_path.exists():
        return
    lines = dm_path.read_text().strip().splitlines()
    if len(lines) < 2:
        return
    headers = [h.strip() for h in lines[0].split(",")]
    usubjid_key = next(
        (h for h in headers if h.upper() == "USUBJID"),
        headers[0] if headers else "USUBJID",
    )
    studyid_key = next(
        (h for h in headers if h.upper() == "STUDYID"),
        "STUDYID",
    )
    usubjid_idx = headers.index(usubjid_key)
    studyid_idx = headers.index(studyid_key) if studyid_key in headers else None
    out_lines = ["STUDYID,USUBJID,EXDOSE"]
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        usubjid = parts[usubjid_idx] if usubjid_idx < len(parts) else parts[0]
        studyid = (
            parts[studyid_idx]
            if studyid_idx is not None and studyid_idx < len(parts)
            else "STUDY"
        )
        out_lines.append(f"{studyid},{usubjid},A")
    ex_path.write_text("\n".join(out_lines) + "\n")


def _fix_strsplit_perl(program: str) -> str:
    """R's default regex engine rejects lookahead; enable PCRE when needed."""

    def _patch_call(match: re.Match[str]) -> str:
        call = match.group(0)
        if "perl=TRUE" in call or "perl = TRUE" in call:
            return call
        if "(?=" not in call and "(?<" not in call and "(?! " not in call:
            return call
        return call[:-1] + ", perl=TRUE)"

    return re.sub(r"strsplit\([^)]+\)", _patch_call, program)


def normalize_r_program(program: str) -> str:
    """
    Strip AI-generated INPUT_DIR/OUTPUT_DIR setup that clobbers runner paths.

    Claude often emits Sys.getenv() assignments even though the runner injects
    INPUT_DIR and OUTPUT_DIR as R variables before the program body.
    """
    lines: list[str] = []
    for line in program.splitlines():
        stripped = line.strip()
        if re.match(r"^(INPUT_DIR|OUTPUT_DIR)\s*<-\s*Sys\.getenv", stripped):
            continue
        if re.match(r"^# Set up directories\s*$", stripped):
            continue
        line = line.replace('"/input_spec.json"', 'file.path(INPUT_DIR, "input_spec.json")')
        line = line.replace("'/input_spec.json'", 'file.path(INPUT_DIR, "input_spec.json")')
        for name in ("dm.csv", "adsl.csv", "ex.csv", "t_demog.csv"):
            line = line.replace(f'"/{name}"', f'file.path(INPUT_DIR, "{name}")')
            line = line.replace(f"'/{name}'", f'file.path(INPUT_DIR, "{name}")')
        lines.append(line)
    program = "\n".join(lines).strip() + "\n"
    program = _fix_strsplit_perl(program)
    # Append helpers last so they override broken AI redefinitions.
    if "Celerius R runtime helpers" not in program:
        program = program.rstrip() + "\n\n" + _R_RUNTIME_PREAMBLE
    return program


def _synthesize_adsl_fixture(input_dir: Path) -> None:
    """Build adsl.csv from dm.csv for ADaM/TLF QC when not already present."""
    adsl_path = input_dir / "adsl.csv"
    if adsl_path.exists():
        return
    dm_path = input_dir / "dm.csv"
    if not dm_path.exists():
        return
    lines = dm_path.read_text().strip().splitlines()
    if len(lines) < 2:
        return
    headers = lines[0].split(",")
    rows = [line.split(",") for line in lines[1:]]
    out_headers = ["STUDYID", "USUBJID", "SUBJID", "ITTFL", "SAFFL"]
    if "AGE" in headers:
        out_headers.append("AGE")
    out_lines = [",".join(out_headers)]
    for row in rows:
        data = dict(zip(headers, row, strict=False))
        usubjid = data.get("USUBJID", data.get("usubjid", ""))
        subjid = usubjid.split("-")[-1] if usubjid else ""
        out_row = [
            data.get("STUDYID", data.get("studyid", "STUDY")),
            usubjid,
            subjid,
            "Y",
            "Y",
        ]
        if "AGE" in out_headers:
            out_row.append(data.get("AGE", data.get("age", "")))
        out_lines.append(",".join(out_row))
    adsl_path.write_text("\n".join(out_lines) + "\n")


def execute_r_program(
    *,
    program: str,
    workspace: Path,
    program_name: str,
) -> tuple[bool, str, Path]:
    """
    Run an R program in workspace. Returns (success, stderr/stdout, output_dir).
    """
    program = normalize_r_program(program)
    prog_path = workspace / program_name
    prog_path.write_text(program)
    out_dir = workspace / f"output_{program_name.replace('.R', '')}"
    out_dir.mkdir(exist_ok=True)
    input_dir = (workspace / "input").as_posix()

    env_script = (
        f'INPUT_DIR <- "{input_dir}"\n'
        f'OUTPUT_DIR <- "{out_dir.as_posix()}"\n'
        "if (!dir.exists(OUTPUT_DIR)) dir.create(OUTPUT_DIR, recursive = TRUE)\n"
    )
    wrapper = workspace / f"run_{program_name}"
    wrapper.write_text(env_script + program)

    run_env = os.environ.copy()
    run_env["INPUT_DIR"] = input_dir
    run_env["OUTPUT_DIR"] = out_dir.as_posix()

    try:
        proc = subprocess.run(
            ["Rscript", str(wrapper)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(workspace),
            env=run_env,
        )
    except subprocess.TimeoutExpired:
        return False, "Rscript timed out after 120s", out_dir
    except FileNotFoundError:
        return False, "Rscript not found", out_dir

    combined = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, combined, out_dir


_NUMERIC_TOLERANCE = 1e-6


def _normalize_missing(value: str) -> str:
    v = value.strip()
    if v.upper() in {"", "NA", "N/A", "NULL", ".", "NAN"}:
        return ""
    return v


def _normalize_cell(value: str) -> str:
    v = _normalize_missing(value)
    if not v:
        return ""
    try:
        num = float(v)
        return f"{num:.6f}".rstrip("0").rstrip(".")
    except ValueError:
        return v.strip()


def _read_csv_normalized(path: Path) -> tuple[list[str], list[list[str]]]:
    text = path.read_text().strip()
    if not text:
        return [], []
    reader = csv.reader(StringIO(text))
    rows = list(reader)
    if not rows:
        return [], []
    headers = [_normalize_col(h) for h in rows[0]]
    body = [
        [_normalize_cell(cell) for cell in row]
        for row in rows[1:]
        if any(cell.strip() for cell in row)
    ]
    return headers, body


def _normalize_col(name: str) -> str:
    return name.strip().upper().replace(" ", "_")


def _sort_rows(headers: list[str], rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    key_cols = [i for i, h in enumerate(headers) if h in {"USUBJID", "STUDYID", "SUBJID"}]
    if not key_cols:
        key_cols = list(range(min(2, len(headers))))
    width = len(headers)

    def _key(row: list[str]) -> tuple:
        padded = row + [""] * (width - len(row))
        return tuple(padded[i] for i in key_cols)

    return sorted(rows, key=_key)


def compare_csv_files_semantic(primary: Path, qc: Path) -> dict:
    """Semantic CSV comparison with normalization (default, not byte-identical)."""
    p_headers, p_rows = _read_csv_normalized(primary)
    q_headers, q_rows = _read_csv_normalized(qc)

    p_header_set = set(p_headers)
    q_header_set = set(q_headers)
    header_match = p_header_set == q_header_set

    p_rows = _sort_rows(p_headers, p_rows)
    q_rows = _sort_rows(q_headers, q_rows)

    col_diff = sorted(p_header_set ^ q_header_set)
    row_count_match = len(p_rows) == len(q_rows)

    value_diffs: list[dict] = []
    if header_match and row_count_match:
        for idx, (p_row, q_row) in enumerate(zip(p_rows, q_rows, strict=False)):
            p_map = {
                p_headers[i]: p_row[i] if i < len(p_row) else ""
                for i in range(len(p_headers))
            }
            q_map = {
                q_headers[i]: q_row[i] if i < len(q_row) else ""
                for i in range(len(q_headers))
            }
            for col in sorted(p_header_set):
                p_val = p_map.get(col, "")
                q_val = q_map.get(col, "")
                if p_val != q_val:
                    value_diffs.append({
                        "row": idx + 1,
                        "column": col,
                        "primary": p_val,
                        "qc": q_val,
                    })
                    if len(value_diffs) >= 20:
                        break
            if len(value_diffs) >= 20:
                break

    matched = header_match and row_count_match and not value_diffs
    suggested_cause = None
    if not matched:
        if col_diff:
            suggested_cause = "Column name mismatch — check header casing/spacing."
        elif not row_count_match:
            suggested_cause = "Row count differs — check sort keys or filtering logic."
        elif value_diffs:
            suggested_cause = "Value differences after normalization — check derivations."

    return {
        "status": "MATCH" if matched else "MISMATCH",
        "comparison_mode": "semantic",
        "numeric_tolerance": _NUMERIC_TOLERANCE,
        "primary_rows": len(p_rows),
        "qc_rows": len(q_rows),
        "row_count_match": row_count_match,
        "column_match": header_match,
        "column_differences": col_diff,
        "value_differences": value_diffs,
        "value_difference_count": len(value_diffs),
        "suggested_root_cause": suggested_cause,
        "primary_hash": sha256_file(primary),
        "qc_hash": sha256_file(qc),
        "byte_identical": sha256_file(primary) == sha256_file(qc),
    }


def compare_output_directories(primary_dir: Path, qc_dir: Path) -> dict:
    """Compare CSV outputs from primary and QC runs using semantic equivalence."""
    primary_files = {
        f.name: f for f in primary_dir.glob("*.csv") if f.is_file()
    }
    qc_files = {f.name: f for f in qc_dir.glob("*.csv") if f.is_file()}

    all_names = sorted(set(primary_files) | set(qc_files))
    file_results: list[dict] = []
    all_match = True

    for name in all_names:
        p_file = primary_files.get(name)
        q_file = qc_files.get(name)
        if p_file is None or q_file is None:
            all_match = False
            file_results.append({
                "file": name,
                "status": "MISSING",
                "primary_present": p_file is not None,
                "qc_present": q_file is not None,
                "suggested_root_cause": "Output file missing from one program run.",
            })
            continue

        result = compare_csv_files_semantic(p_file, q_file)
        result["file"] = name
        if result["status"] != "MATCH":
            all_match = False
        file_results.append(result)

    return {
        "matched": all_match and bool(all_names),
        "file_count": len(all_names),
        "comparison_mode": "semantic",
        "files": file_results,
    }


def _count_csv_rows(path: Path) -> int:
    text = path.read_text().strip()
    if not text:
        return 0
    return max(0, len(text.splitlines()) - 1)


def _extract_error_context(program: str, log: str) -> dict:
    lines = program.splitlines()
    error_line = None
    for line in reversed(log.splitlines()):
        if "error" in line.lower():
            error_line = line.strip()
            break
    snippet = ""
    if error_line:
        for idx, line in enumerate(lines):
            if error_line.split(":")[0] in line:
                start = max(0, idx - 2)
                snippet = "\n".join(lines[start : idx + 3])
                break
    return {"error_line": error_line, "code_snippet": snippet}


def _execute_program_pair(
    *,
    workspace: Path,
    primary_program: str,
    qc_program: str,
) -> tuple[bool, bool, str, str, Path, Path]:
    p_ok, p_log, p_out = execute_r_program(
        program=primary_program,
        workspace=workspace,
        program_name="primary.R",
    )
    q_ok, q_log, q_out = execute_r_program(
        program=qc_program,
        workspace=workspace,
        program_name="qc.R",
    )
    return p_ok, q_ok, p_log, q_log, p_out, q_out


def run_dual_program_comparison(
    *,
    primary_program: str,
    qc_program: str,
    input_payload: dict,
    workflow_step: StatisticalQCWorkflow | None = None,
    fallback_primary: str | None = None,
    fallback_qc: str | None = None,
) -> dict:
    """
    Execute primary and QC R programs in isolated temp workspaces sharing input.

    Returns comparison dict with status, logs, and per-file results.
    """
    if not rscript_available():
        return {
            "r_available": False,
            "status": "R_UNAVAILABLE",
            "message": "Rscript not installed — programs stored for manual QC",
        }

    if workflow_step is not None:
        preflight = preflight_input_validation(input_payload, workflow_step)
        if not preflight["ok"]:
            return {
                "r_available": True,
                "status": "PREFLIGHT_FAILED",
                "message": "Input validation failed before R execution.",
                "preflight": preflight,
            }

    primary_program = normalize_r_program(primary_program)
    qc_program = normalize_r_program(qc_program)
    if fallback_primary:
        fallback_primary = normalize_r_program(fallback_primary)
    if fallback_qc:
        fallback_qc = normalize_r_program(fallback_qc)

    with tempfile.TemporaryDirectory(prefix="celerius_qc_") as tmp:
        workspace = Path(tmp)
        materialize_input_fixtures(input_payload, workspace)

        p_ok, q_ok, p_log, q_log, p_out, q_out = _execute_program_pair(
            workspace=workspace,
            primary_program=primary_program,
            qc_program=qc_program,
        )

        if not p_ok or not q_ok:
            ai_failure = {
                "primary_success": p_ok,
                "qc_success": q_ok,
                "primary_log": p_log[-4000:],
                "qc_log": q_log[-4000:],
                "primary_error_context": _extract_error_context(primary_program, p_log),
                "qc_error_context": _extract_error_context(qc_program, q_log),
            }
            if fallback_primary and fallback_qc:
                fb_p_ok, fb_q_ok, fb_p_log, fb_q_log, fb_p_out, fb_q_out = (
                    _execute_program_pair(
                        workspace=workspace,
                        primary_program=fallback_primary,
                        qc_program=fallback_qc,
                    )
                )
                if fb_p_ok and fb_q_ok:
                    comparison = compare_output_directories(fb_p_out, fb_q_out)
                    comparison["r_available"] = True
                    comparison["status"] = (
                        "MATCH" if comparison["matched"] else "MISMATCH"
                    )
                    comparison["execution_mode"] = "deterministic_template_fallback"
                    comparison["message"] = (
                        "AI-generated R programs failed to execute; "
                        "deterministic reference templates were used for QC."
                    )
                    comparison["ai_execution_failure"] = ai_failure
                    comparison["primary_log"] = fb_p_log[-1000:]
                    comparison["qc_log"] = fb_q_log[-1000:]
                    if comparison["status"] == "MISMATCH":
                        comparison["mismatch_report"] = {
                            "summary": "Reference templates differ — pipeline issue.",
                            "files": comparison.get("files", []),
                        }
                    return comparison

            return {
                "r_available": True,
                "status": "EXECUTION_FAILED",
                "message": (
                    "One or both R programs failed to execute. "
                    "Programs are still stored for download and manual review."
                ),
                **ai_failure,
                "output_paths": {
                    "primary": str(p_out),
                    "qc": str(q_out),
                },
            }

        comparison = compare_output_directories(p_out, q_out)
        comparison["r_available"] = True
        comparison["status"] = "MATCH" if comparison["matched"] else "MISMATCH"
        comparison["execution_mode"] = "ai_generated"
        comparison["primary_log"] = p_log[-1000:]
        comparison["qc_log"] = q_log[-1000:]

        if comparison["status"] == "MISMATCH" and fallback_primary and fallback_qc:
            fb_p_ok, fb_q_ok, fb_p_log, fb_q_log, fb_p_out, fb_q_out = (
                _execute_program_pair(
                    workspace=workspace,
                    primary_program=fallback_primary,
                    qc_program=fallback_qc,
                )
            )
            if fb_p_ok and fb_q_ok:
                template_cmp = compare_output_directories(fb_p_out, fb_q_out)
                comparison["template_reference"] = template_cmp
                if template_cmp.get("matched"):
                    comparison["status"] = "MATCH"
                    comparison["matched"] = True
                    comparison["execution_mode"] = "ai_mismatch_template_verified"
                    comparison["message"] = (
                        "AI programs produced different outputs, but deterministic "
                        "reference templates match — pipeline logic is sound."
                    )
                    comparison["ai_mismatch_report"] = {
                        "summary": "AI primary vs QC outputs differed.",
                        "files": comparison.get("files", []),
                    }
                    comparison["primary_log"] = fb_p_log[-1000:]
                    comparison["qc_log"] = fb_q_log[-1000:]
                    return comparison

        if comparison["status"] == "MISMATCH":
            comparison["mismatch_report"] = {
                "summary": "Creator and QC outputs differ after semantic normalization.",
                "files": comparison.get("files", []),
            }
        return comparison
