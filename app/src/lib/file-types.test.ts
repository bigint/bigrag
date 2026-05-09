import { describe, expect, it } from "vitest";
import { acceptAttribute, filterBlockedFiles, getAllowedFileTypes } from "./file-types";

describe("file type helpers", () => {
  it("normalizes allowed file types from collection metadata", () => {
    expect(getAllowedFileTypes({ allowed_file_types: ["PDF", "md", 5] })).toEqual(["pdf", "md"]);
    expect(getAllowedFileTypes({ allowed_file_types: "pdf" })).toEqual([]);
  });

  it("splits accepted and rejected files by extension", () => {
    const files = [new File(["x"], "a.PDF"), new File(["x"], "b.exe"), new File(["x"], "c")];

    expect(filterBlockedFiles(files, ["pdf"])).toEqual({
      accepted: [files[0]],
      rejected: [files[1], files[2]],
    });
  });

  it("builds an accept attribute from explicit or default file types", () => {
    expect(acceptAttribute(["pdf", "md"])).toBe(".pdf,.md");
    expect(acceptAttribute([])).toContain(".pdf");
  });
});
