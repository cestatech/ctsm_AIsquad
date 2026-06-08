"""Execute R programs in an isolated workspace and compare outputs."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


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
    return "\n".join(lines).strip() + "\n"


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


def compare_output_directories(primary_dir: Path, qc_dir: Path) -> dict:
    """Compare CSV outputs from primary and QC runs."""
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
            })
            continue

        p_hash = sha256_file(p_file)
        q_hash = sha256_file(q_file)
        matched = p_hash == q_hash
        if not matched:
            all_match = False
        file_results.append({
            "file": name,
            "status": "MATCH" if matched else "MISMATCH",
            "primary_hash": p_hash,
            "qc_hash": q_hash,
            "primary_rows": _count_csv_rows(p_file),
            "qc_rows": _count_csv_rows(q_file),
        })

    return {
        "matched": all_match and bool(all_names),
        "file_count": len(all_names),
        "files": file_results,
    }


def _count_csv_rows(path: Path) -> int:
    text = path.read_text().strip()
    if not text:
        return 0
    return max(0, len(text.splitlines()) - 1)


def run_dual_program_comparison(
    *,
    primary_program: str,
    qc_program: str,
    input_payload: dict,
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

    with tempfile.TemporaryDirectory(prefix="celerius_qc_") as tmp:
        workspace = Path(tmp)
        materialize_input_fixtures(input_payload, workspace)

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

        if not p_ok or not q_ok:
            return {
                "r_available": True,
                "status": "EXECUTION_FAILED",
                "message": (
                    "One or both R programs failed to execute. "
                    "Programs are still stored for download and manual review."
                ),
                "primary_success": p_ok,
                "qc_success": q_ok,
                "primary_log": p_log[-2000:],
                "qc_log": q_log[-2000:],
            }

        comparison = compare_output_directories(p_out, q_out)
        comparison["r_available"] = True
        comparison["status"] = "MATCH" if comparison["matched"] else "MISMATCH"
        comparison["primary_log"] = p_log[-1000:]
        comparison["qc_log"] = q_log[-1000:]
        return comparison
