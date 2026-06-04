"""Unit tests for the internal CDISC conformance validation engine.

run_cdisc_validation() is a pure function — no DB, no mocks needed.
Each test builds a minimal content dict and asserts on rule outcomes.
"""

from __future__ import annotations

from app.services.cdisc_validation_engine import FAIL, PASS, run_cdisc_validation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _findings_by_id(result: dict) -> dict[str, dict]:
    return {f["rule_id"]: f for f in result["findings"]}


def _sdtm_domain(name: str, variables: list[dict], **extras) -> dict:
    base = {"dataset": name, "variables": variables}
    base.update(extras)
    return base


def _var(name: str, **kwargs) -> dict:
    return {"variable": name, **kwargs}


# ---------------------------------------------------------------------------
# Generic rules (GEN-001 to GEN-004)
# ---------------------------------------------------------------------------


class TestGenericRules:
    def test_empty_content_fails_gen001(self):
        result = run_cdisc_validation({}, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["GEN-001"]["status"] == FAIL

    def test_content_present_passes_gen001(self):
        content = {
            "document_type": "PROTOCOL",
            "version": "1.0",
            "title": "Some Protocol",
        }
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["GEN-001"]["status"] == PASS

    def test_mismatched_document_type_fails_gen002(self):
        content = {"document_type": "ICF", "version": "1.0", "title": "x"}
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["GEN-002"]["status"] == FAIL

    def test_matching_document_type_passes_gen002(self):
        content = {"document_type": "PROTOCOL", "version": "1.0", "title": "x"}
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["GEN-002"]["status"] == PASS

    def test_missing_version_fails_gen003(self):
        content = {"document_type": "PROTOCOL", "title": "x"}
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["GEN-003"]["status"] == FAIL

    def test_version_present_passes_gen003(self):
        content = {"document_type": "PROTOCOL", "version": "1.0", "title": "x"}
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["GEN-003"]["status"] == PASS

    def test_missing_regulatory_refs_fails_gen004(self):
        content = {"document_type": "PROTOCOL", "version": "1.0", "title": "x"}
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["GEN-004"]["status"] == FAIL

    def test_regulatory_refs_present_passes_gen004(self):
        content = {
            "document_type": "PROTOCOL",
            "version": "1.0",
            "title": "x",
            "regulatory_references": ["ICH E6(R2)"],
        }
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["GEN-004"]["status"] == PASS


# ---------------------------------------------------------------------------
# SDTM rules
# ---------------------------------------------------------------------------


def _minimal_sdtm_content() -> dict:
    return {
        "document_type": "SDTM_DATASET",
        "version": "1.0",
        "regulatory_references": ["CDISC SDTM IG v3.3"],
        "define_xml_version": "2.1",
        "domains": [
            _sdtm_domain(
                "DM",
                [
                    _var("STUDYID"),
                    _var("USUBJID"),
                    _var("RFSTDTC"),
                    _var("RFENDTC"),
                    _var("SEX", controlled_terminology="NCI (C66731)"),
                    _var("RACE", controlled_terminology="NCI (C74457)"),
                    _var("ETHNIC", controlled_terminology="NCI (C66790)"),
                    _var("ARMCD"),
                    _var("ARM"),
                    _var("COUNTRY"),
                    _var("AGE"),
                    _var("AGEU"),
                ],
            )
        ],
    }


class TestSDTMRules:
    def test_no_domains_fails_sdtm001(self):
        content = {
            "document_type": "SDTM_DATASET",
            "version": "1.0",
            "regulatory_references": ["CDISC SDTM IG v3.3"],
        }
        result = run_cdisc_validation(content, "SDTM_DATASET")
        findings = _findings_by_id(result)
        assert findings["SDTM-001"]["status"] == FAIL

    def test_domain_present_no_sdtm001_failure(self):
        # SDTM-001 only appears in findings when it FAILS (no domains).
        # When domains are present the rule is satisfied and omitted from findings.
        result = run_cdisc_validation(_minimal_sdtm_content(), "SDTM_DATASET")
        findings = _findings_by_id(result)
        assert "SDTM-001" not in findings or findings["SDTM-001"]["status"] == PASS

    def test_missing_studyid_fails_sdtm002(self):
        content = _minimal_sdtm_content()
        content["domains"][0]["variables"] = [_var("USUBJID")]
        result = run_cdisc_validation(content, "SDTM_DATASET")
        findings = _findings_by_id(result)
        assert findings["SDTM-002"]["status"] == FAIL

    def test_studyid_present_passes_sdtm002(self):
        result = run_cdisc_validation(_minimal_sdtm_content(), "SDTM_DATASET")
        findings = _findings_by_id(result)
        assert findings["SDTM-002"]["status"] == PASS

    def test_dm_missing_variables_fails_sdtm005(self):
        content = _minimal_sdtm_content()
        # Keep only STUDYID and USUBJID — missing the rest of DM required
        content["domains"][0]["variables"] = [_var("STUDYID"), _var("USUBJID")]
        result = run_cdisc_validation(content, "SDTM_DATASET")
        findings = _findings_by_id(result)
        assert findings["SDTM-005"]["status"] == FAIL
        assert "RFSTDTC" in findings["SDTM-005"]["message"]

    def test_dm_all_variables_passes_sdtm005(self):
        result = run_cdisc_validation(_minimal_sdtm_content(), "SDTM_DATASET")
        findings = _findings_by_id(result)
        assert findings["SDTM-005"]["status"] == PASS

    def test_ae_domain_checked_for_ae_variables(self):
        content = _minimal_sdtm_content()
        ae = _sdtm_domain(
            "AE",
            [
                _var("STUDYID"),
                _var("USUBJID"),
                _var("AETERM"),
                # missing AEDECOD, AEBODSYS, AESEV, AESER, AEOUT
            ],
        )
        content["domains"].append(ae)
        result = run_cdisc_validation(content, "SDTM_DATASET")
        findings = _findings_by_id(result)
        assert findings["SDTM-006"]["status"] == FAIL

    def test_missing_sdtm_ig_reference_fails_sdtm010(self):
        content = _minimal_sdtm_content()
        content["regulatory_references"] = ["ICH E6"]  # no SDTM ref
        result = run_cdisc_validation(content, "SDTM_DATASET")
        findings = _findings_by_id(result)
        assert findings["SDTM-010"]["status"] == FAIL

    def test_sdtm_ig_reference_passes_sdtm010(self):
        result = run_cdisc_validation(_minimal_sdtm_content(), "SDTM_DATASET")
        findings = _findings_by_id(result)
        assert findings["SDTM-010"]["status"] == PASS

    def test_result_summary_counts(self):
        result = run_cdisc_validation(_minimal_sdtm_content(), "SDTM_DATASET")
        assert result["total_checks"] == len(result["findings"])
        assert (
            result["passed_checks"] + result["failed_checks"] <= result["total_checks"]
        )
        assert result["rule_set"] == "CDISC-INTERNAL-1.0"


# ---------------------------------------------------------------------------
# ADaM rules
# ---------------------------------------------------------------------------


def _minimal_adam_content() -> dict:
    return {
        "document_type": "ADAM_DATASET",
        "version": "1.0",
        "regulatory_references": ["CDISC ADaM IG v1.1"],
        "adam_ig_version": "1.1",
        "traceability_notes": ["ADSL derived from SDTM DM"],
        "datasets": [
            {
                "dataset": "ADSL",
                "variables": [
                    _var("USUBJID", derivation="From DM.USUBJID"),
                    _var("SUBJID", derivation="From DM.SUBJID"),
                    _var("STUDYID", derivation="From DM.STUDYID"),
                ],
                "population_flags": [
                    {"variable": "ITTFL"},
                    {"variable": "SAFFL"},
                ],
            }
        ],
    }


class TestADaMRules:
    def test_no_datasets_fails_adam001(self):
        content = {
            "document_type": "ADAM_DATASET",
            "version": "1.0",
            "regulatory_references": ["CDISC ADaM IG"],
        }
        result = run_cdisc_validation(content, "ADAM_DATASET")
        findings = _findings_by_id(result)
        assert findings["ADAM-001"]["status"] == FAIL

    def test_missing_adsl_fails_adam002(self):
        content = _minimal_adam_content()
        content["datasets"] = [{"dataset": "ADLB", "variables": []}]
        result = run_cdisc_validation(content, "ADAM_DATASET")
        findings = _findings_by_id(result)
        assert findings["ADAM-002"]["status"] == FAIL

    def test_adsl_present_passes_adam002(self):
        result = run_cdisc_validation(_minimal_adam_content(), "ADAM_DATASET")
        findings = _findings_by_id(result)
        assert findings["ADAM-002"]["status"] == PASS

    def test_adsl_missing_usubjid_fails_adam003(self):
        content = _minimal_adam_content()
        content["datasets"][0]["variables"] = [
            _var("SUBJID", derivation="x"),
            _var("STUDYID", derivation="x"),
        ]
        result = run_cdisc_validation(content, "ADAM_DATASET")
        findings = _findings_by_id(result)
        assert findings["ADAM-003"]["status"] == FAIL

    def test_no_population_flags_fails_adam004(self):
        content = _minimal_adam_content()
        content["datasets"][0]["population_flags"] = []
        result = run_cdisc_validation(content, "ADAM_DATASET")
        findings = _findings_by_id(result)
        assert findings["ADAM-004"]["status"] == FAIL

    def test_ittfl_missing_fails_adam005(self):
        content = _minimal_adam_content()
        content["datasets"][0]["population_flags"] = [{"variable": "SAFFL"}]
        result = run_cdisc_validation(content, "ADAM_DATASET")
        findings = _findings_by_id(result)
        assert findings["ADAM-005"]["status"] == FAIL

    def test_ittfl_present_passes_adam005(self):
        result = run_cdisc_validation(_minimal_adam_content(), "ADAM_DATASET")
        findings = _findings_by_id(result)
        assert findings["ADAM-005"]["status"] == PASS

    def test_variable_without_derivation_fails_adam006(self):
        content = _minimal_adam_content()
        content["datasets"][0]["variables"].append(_var("TRTPCD", derivation=""))
        result = run_cdisc_validation(content, "ADAM_DATASET")
        adam006 = [f for f in result["findings"] if f["rule_id"] == "ADAM-006"]
        assert any(f["status"] == FAIL for f in adam006)


# ---------------------------------------------------------------------------
# Protocol rules
# ---------------------------------------------------------------------------


def _minimal_protocol_content() -> dict:
    return {
        "document_type": "PROTOCOL",
        "version": "1.0",
        "regulatory_references": ["ICH E6(R2)"],
        "synopsis": {"title": "Study Synopsis"},
        "objectives": {"primary": "To assess efficacy of Drug X"},
        "study_design": {"type": "randomized double-blind"},
        "eligibility": {
            "inclusion_criteria": ["Age >= 18"],
            "exclusion_criteria": ["Prior treatment"],
        },
        "endpoints": {"primary": "Overall survival at 12 months"},
        "statistical_considerations": {"method": "Cox proportional hazards"},
        "safety_monitoring": {"committee": "DSMB"},
    }


class TestProtocolRules:
    def test_full_protocol_passes_all_rules(self):
        result = run_cdisc_validation(_minimal_protocol_content(), "PROTOCOL")
        errors = [
            f
            for f in result["findings"]
            if f["status"] == FAIL and f["severity"] == "ERROR"
        ]
        assert errors == [], f"Unexpected errors: {[e['rule_id'] for e in errors]}"

    def test_missing_synopsis_fails_prot001(self):
        content = _minimal_protocol_content()
        del content["synopsis"]
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["PROT-001"]["status"] == FAIL

    def test_missing_primary_objective_fails_prot002(self):
        content = _minimal_protocol_content()
        content["objectives"] = {}
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["PROT-002"]["status"] == FAIL

    def test_missing_study_design_fails_prot003(self):
        content = _minimal_protocol_content()
        del content["study_design"]
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["PROT-003"]["status"] == FAIL

    def test_missing_exclusion_criteria_fails_prot004(self):
        content = _minimal_protocol_content()
        content["eligibility"] = {"inclusion_criteria": ["Age >= 18"]}
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["PROT-004"]["status"] == FAIL

    def test_missing_primary_endpoint_fails_prot005(self):
        content = _minimal_protocol_content()
        content["endpoints"] = {}
        result = run_cdisc_validation(content, "PROTOCOL")
        findings = _findings_by_id(result)
        assert findings["PROT-005"]["status"] == FAIL


# ---------------------------------------------------------------------------
# Unknown artifact type
# ---------------------------------------------------------------------------


class TestUnknownArtifactType:
    def test_unknown_type_adds_gen005_pass(self):
        content = {"document_type": "TLF", "version": "1.0", "title": "x"}
        result = run_cdisc_validation(content, "TLF")
        findings = _findings_by_id(result)
        assert "GEN-005" in findings
        assert findings["GEN-005"]["status"] == PASS

    def test_result_structure_always_present(self):
        result = run_cdisc_validation({}, "UNKNOWN_TYPE")
        assert "total_checks" in result
        assert "passed_checks" in result
        assert "failed_checks" in result
        assert "findings" in result
        assert "rule_set" in result
        assert isinstance(result["findings"], list)
