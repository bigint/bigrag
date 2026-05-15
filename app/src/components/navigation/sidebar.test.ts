import { describe, expect, it } from "vitest";
import { getSidebarNavItems } from "./sidebar";

describe("sidebar navigation", () => {
  it("shows operational admin destinations before settings", () => {
    const adminItems = getSidebarNavItems("admin");
    const hrefs = adminItems.map((item) => item.href);

    expect(hrefs).toContain("/backups");
    expect(hrefs).toContain("/usage");
    expect(hrefs).toContain("/audit");
    expect(hrefs.indexOf("/usage")).toBeLessThan(hrefs.indexOf("/settings"));
    expect(hrefs.indexOf("/audit")).toBeLessThan(hrefs.indexOf("/settings"));
    expect(hrefs.indexOf("/backups")).toBeLessThan(hrefs.indexOf("/settings"));
  });

  it("hides admin operational navigation for non-admin users", () => {
    expect(getSidebarNavItems("member").map((item) => item.href)).not.toContain("/usage");
    expect(getSidebarNavItems("member").map((item) => item.href)).not.toContain("/audit");
    expect(getSidebarNavItems("member").map((item) => item.href)).not.toContain("/backups");
  });
});
