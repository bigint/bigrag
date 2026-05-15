import { describe, expect, it } from "vitest";
import { getSidebarNavGroups, getSidebarNavItems, isSidebarItemActive } from "./sidebar";

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

  it("groups admin destinations by sidebar section", () => {
    const groups = getSidebarNavGroups("admin");
    const labelsByGroup = Object.fromEntries(
      groups.map((group) => [group.label, group.items.map((item) => item.label)]),
    );

    expect(groups.map((group) => group.label)).toEqual([
      "Workspace",
      "Interfaces",
      "Observability",
      "Administration",
    ]);
    expect(labelsByGroup.Workspace).toEqual(["Overview", "Collections", "Models", "Chat", "Evals"]);
    expect(labelsByGroup.Interfaces).toEqual(["MCP", "API Keys", "Webhooks", "Connectors"]);
    expect(labelsByGroup.Observability).toEqual(["Access Logs", "Usage", "Audit"]);
    expect(labelsByGroup.Administration).toEqual(["Backups", "Vector Storage", "Settings"]);

    const labels = groups.flatMap((group) => group.items.map((item) => item.label));

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
