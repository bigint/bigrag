import { describe, expect, it } from "vitest";
import { formatBytes, formatNumber, formatRelative } from "./format";

describe("format helpers", () => {
  it("formats bytes with stable units", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("formats compact numbers only above the threshold", () => {
    expect(formatNumber(9999)).toBe("9,999");
    expect(formatNumber(12000)).toBe("12K");
  });

  it("handles invalid relative dates", () => {
    expect(formatRelative(null)).toBe("—");
    expect(formatRelative("not-a-date")).toBe("—");
  });
});
