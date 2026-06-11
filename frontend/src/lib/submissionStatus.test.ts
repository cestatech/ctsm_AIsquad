import { describe, expect, it } from "vitest";
import {
  deriveFileGrade,
  derivePackageDisplayState,
  shouldPollPackage,
} from "./submissionStatus";

describe("submissionStatus", () => {
  it("polls while packaging or fresh draft without error", () => {
    expect(
      shouldPollPackage({ status: "PACKAGING", error_message: null })
    ).toBe(true);
    expect(shouldPollPackage({ status: "DRAFT", error_message: null })).toBe(
      true
    );
  });

  it("stops polling when ready or failed", () => {
    expect(shouldPollPackage({ status: "READY", error_message: null })).toBe(
      false
    );
    expect(
      shouldPollPackage({
        status: "DRAFT",
        error_message: "Assembly failed",
      })
    ).toBe(false);
  });

  it("derives display states", () => {
    expect(
      derivePackageDisplayState({ status: "READY", error_message: null })
    ).toBe("ready");
    expect(
      derivePackageDisplayState({
        status: "PACKAGING",
        error_message: null,
      })
    ).toBe("packaging");
    expect(
      derivePackageDisplayState({
        status: "DRAFT",
        error_message: "disk full",
      })
    ).toBe("failed");
    expect(derivePackageDisplayState(null)).toBe("idle");
  });

  it("treats packaging-with-error as failed even if status lags", () => {
    expect(
      derivePackageDisplayState({
        status: "PACKAGING",
        error_message: "Background assembly failed",
      })
    ).toBe("failed");
  });

  it("uses API grade when present and falls back for legacy packages", () => {
    expect(
      deriveFileGrade({ path: "m5/define.xml", grade: "generated" })
    ).toBe("generated");
    expect(
      deriveFileGrade({ path: "m5/reviewers-guide.pdf" })
    ).toBe("placeholder");
    expect(deriveFileGrade({ path: "tlf/abc.rtf" })).toBe("generated");
  });
});
