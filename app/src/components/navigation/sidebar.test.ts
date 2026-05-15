import { describe, expect, it } from "vitest";
import { getSidebarNavItems, isSidebarItemActive } from "./sidebar";

describe("sidebar navigation", () => {
  it("keeps admin-only destinations out of member navigation", () => {
    const labels = getSidebarNavItems("member").map((item) => item.label);

    expect(labels).toContain("Overview");
    expect(labels).toContain("Collections");
    expect(labels).not.toContain("Usage");
    expect(labels).not.toContain("Audit");
    expect(labels).not.toContain("Connectors");
    expect(labels).not.toContain("Backups");
    expect(labels).not.toContain("Vector Storage");
    expect(labels).not.toContain("Settings");
  });

  it("shows operational destinations as top-level admin destinations", () => {
    const labels = getSidebarNavItems("admin").map((item) => item.label);

    expect(labels).toContain("Usage");
    expect(labels).toContain("Audit");
    expect(labels).toContain("Connectors");
    expect(labels).toContain("Backups");
    expect(labels).toContain("Vector Storage");
    expect(labels.indexOf("Usage")).toBeGreaterThan(labels.indexOf("Access Logs"));
    expect(labels.indexOf("Audit")).toBeGreaterThan(labels.indexOf("Usage"));
    expect(labels.indexOf("Connectors")).toBeGreaterThan(labels.indexOf("Webhooks"));
    expect(labels.indexOf("Backups")).toBeGreaterThan(labels.indexOf("Connectors"));
    expect(labels.indexOf("Vector Storage")).toBeGreaterThan(labels.indexOf("Backups"));
    expect(labels.indexOf("Usage")).toBeLessThan(labels.indexOf("Settings"));
    expect(labels.indexOf("Audit")).toBeLessThan(labels.indexOf("Settings"));
    expect(labels.indexOf("Connectors")).toBeLessThan(labels.indexOf("Settings"));
    expect(labels.indexOf("Backups")).toBeLessThan(labels.indexOf("Settings"));
    expect(labels.indexOf("Vector Storage")).toBeLessThan(labels.indexOf("Settings"));
  });

  it("matches active routes by exact path or descendants", () => {
    expect(isSidebarItemActive("/connectors", "/connectors")).toBe(true);
    expect(isSidebarItemActive("/connectors/google", "/connectors")).toBe(true);
    expect(isSidebarItemActive("/collections/docs/connectors", "/connectors")).toBe(false);
    expect(isSidebarItemActive("/vector-storage", "/vector-storage")).toBe(true);
  });
});
