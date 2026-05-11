import { describe, expect, it } from "vitest";
import { apiUrl, ragComputerApiUrl } from "./runtime";

describe("runtime config", () => {
  it("uses the default API URL in tests", () => {
    expect(ragComputerApiUrl).toBe("http://localhost:4000");
  });

  it("joins API paths without duplicate slashes", () => {
    expect(apiUrl("/v1/collections")).toBe("http://localhost:4000/v1/collections");
  });
});
