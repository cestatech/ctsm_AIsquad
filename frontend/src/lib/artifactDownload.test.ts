import { describe, expect, it } from "vitest";
import {
  getArtifactDownloadConfig,
  getArtifactDownloadOptions,
} from "./artifactDownload";

describe("artifact download options", () => {
  it("returns Word download for protocol artifacts", () => {
    expect(getArtifactDownloadConfig("PROTOCOL")).toEqual({
      label: "Download Word",
      format: "docx",
      primary: true,
    });
  });

  it("returns PDF download for ICF artifacts", () => {
    expect(getArtifactDownloadConfig("ICF")).toEqual({
      label: "Download PDF",
      format: "pdf",
      primary: true,
    });
  });

  it("returns ZIP download for SDTM artifacts", () => {
    expect(getArtifactDownloadConfig("SDTM_DATASET")).toEqual({
      label: "Download ZIP",
      format: "zip",
      primary: true,
    });
  });

  it("includes define.xml as secondary SDTM download", () => {
    const options = getArtifactDownloadOptions("SDTM_DATASET");
    expect(options).toHaveLength(2);
    expect(options[1]).toEqual({
      label: "Download define.xml",
      format: "xml",
    });
  });

  it("returns null for non-synthetic OTHER artifacts", () => {
    expect(
      getArtifactDownloadConfig("OTHER", { name: "Misc Notes" })
    ).toBeNull();
  });

  it("returns CSV for synthetic OTHER artifacts", () => {
    expect(
      getArtifactDownloadConfig("OTHER", {
        name: "Synthetic Data Run",
        description: "SYNTHETIC patient-level CSV",
      })
    ).toEqual({
      label: "Download CSV",
      format: "csv",
      primary: true,
    });
  });
});
