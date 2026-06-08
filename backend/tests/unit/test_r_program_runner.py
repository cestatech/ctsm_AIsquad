"""Unit tests for R program runner and output comparison."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.r_program_runner import (
    compare_output_directories,
    materialize_input_fixtures,
    normalize_r_program,
    run_dual_program_comparison,
    sha256_file,
)
from app.services.dual_programmer_qc_service import (
    _primary_sdtm_template,
    _qc_sdtm_template,
)


class TestMaterializeFixtures:
    def test_writes_domain_csv_and_adsl(self, tmp_path: Path):
        payload = {
            "domains": [{
                "domain": "DM",
                "observations": [
                    {"STUDYID": "S1", "USUBJID": "S1-001", "AGE": "45"},
                ],
            }],
        }
        input_dir = materialize_input_fixtures(payload, tmp_path)
        assert (input_dir / "dm.csv").exists()
        assert (input_dir / "adsl.csv").exists()


class TestCompareOutputs:
    def test_detects_match(self, tmp_path: Path):
        p_dir = tmp_path / "primary"
        q_dir = tmp_path / "qc"
        p_dir.mkdir()
        q_dir.mkdir()
        content = "x,y\n1,2\n"
        (p_dir / "out.csv").write_text(content)
        (q_dir / "out.csv").write_text(content)

        result = compare_output_directories(p_dir, q_dir)
        assert result["matched"] is True
        assert result["files"][0]["status"] == "MATCH"

    def test_detects_mismatch(self, tmp_path: Path):
        p_dir = tmp_path / "primary"
        q_dir = tmp_path / "qc"
        p_dir.mkdir()
        q_dir.mkdir()
        (p_dir / "out.csv").write_text("a\n1\n")
        (q_dir / "out.csv").write_text("a\n2\n")

        result = compare_output_directories(p_dir, q_dir)
        assert result["matched"] is False
        assert result["files"][0]["status"] == "MISMATCH"


class TestSha256:
    def test_hash_stable(self, tmp_path: Path):
        f = tmp_path / "f.csv"
        f.write_text("test")
        assert sha256_file(f) == sha256_file(f)


class TestNormalizeRProgram:
    def test_strips_sys_getenv_path_setup(self):
        program = """# Set up directories
INPUT_DIR <- Sys.getenv("INPUT_DIR")
OUTPUT_DIR <- Sys.getenv("OUTPUT_DIR")
x <- 1
"""
        normalized = normalize_r_program(program)
        assert "Sys.getenv" not in normalized
        assert "x <- 1" in normalized

    def test_rewrites_absolute_input_paths(self):
        program = 'dm <- read.csv("/dm.csv")\n'
        normalized = normalize_r_program(program)
        assert 'file.path(INPUT_DIR, "dm.csv")' in normalized


class TestRunDualProgramComparison:
    def test_templates_execute_when_r_available(self):
        payload = {
            "domains": [{
                "domain": "DM",
                "observations": [
                    {"STUDYID": "S1", "USUBJID": "S1-001", "AGE": "45"},
                ],
            }],
        }
        result = run_dual_program_comparison(
            primary_program=_primary_sdtm_template(),
            qc_program=_qc_sdtm_template(),
            input_payload=payload,
        )
        if result.get("r_available") is False:
            pytest.skip("Rscript not installed in test environment")
        assert result["status"] in {"MATCH", "MISMATCH"}
        assert result.get("primary_success", True) is not False
