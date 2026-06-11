import { describe, expect, it } from "vitest";
import {
  buildDerivationIndex,
  defaultSdtmDomainCode,
  isOpenValidationFinding,
  normalizeSdtmVariable,
  sdtmReviewPath,
} from "./sdtm";
import type { ValidationEvidence } from "@/types";

describe("sdtm api helpers", () => {
  it("builds review path", () => {
    expect(sdtmReviewPath("study-1", "artifact-1")).toBe(
      "/studies/study-1/sdtm/artifact-1"
    );
  });

  it("defaults domain tab to DM when present", () => {
    expect(
      defaultSdtmDomainCode([
        { domain: "AE", variables: [] },
        { domain: "DM", variables: [] },
      ])
    ).toBe("DM");
  });

  it("normalizes variable metadata with derivation index", () => {
    const index = buildDerivationIndex({
      domains: [],
      derived_variables: [{ variable: "DM.AGE", logic: "Age at consent" }],
    });
    const variable = normalizeSdtmVariable(
      { variable: "AGE", label: "Age", type: "num", origin: "Derived" },
      "DM",
      index
    );
    expect(variable.name).toBe("AGE");
    expect(variable.label).toBe("Age");
    expect(variable.dataType).toBe("float");
    expect(variable.origin).toBe("Derived");
    expect(variable.derivation).toBe("Age at consent");
  });

  it("counts open validation findings", () => {
    const open: ValidationEvidence = {
      id: "1",
      organization_id: "org",
      study_id: "study",
      validation_run_id: "run",
      rule_id: "SDTM-001",
      rule_name: "Rule",
      rule_category: "CDISC",
      cdisc_standard: "SDTM-IG-3.3",
      subject_type: "artifact",
      subject_field: "DM.AGE",
      status: "FAIL",
      finding_severity: "ERROR",
      finding_message: "Missing derivation",
      finding_details: {},
      is_ai_evaluated: false,
      ai_decision_id: null,
      waived_by_id: null,
      waiver_reason: null,
      waived_at: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    expect(isOpenValidationFinding(open)).toBe(true);
    expect(isOpenValidationFinding({ ...open, status: "PASS" })).toBe(false);
  });
});
