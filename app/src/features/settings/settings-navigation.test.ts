import { describe, expect, it } from "vitest";
import {
  DATA_SETTINGS_GROUPS,
  DEFAULT_SETTINGS_TAB,
  getSettingsNavItem,
  getSettingsTab,
  isSettingsTab,
  SETTINGS_NAV_ITEMS,
  settingsSectionLabel,
} from "./settings-navigation";

describe("settings navigation", () => {
  it("falls back to the default tab for empty or unknown input", () => {
    expect(getSettingsTab(undefined)).toBe(DEFAULT_SETTINGS_TAB);
    expect(getSettingsTab("missing")).toBe(DEFAULT_SETTINGS_TAB);
  });

  it("accepts valid settings tabs", () => {
    expect(isSettingsTab("security")).toBe(true);
    expect(isSettingsTab("server")).toBe(false);
    expect(isSettingsTab("models")).toBe(false);
    expect(isSettingsTab("connectors")).toBe(false);
    expect(isSettingsTab("backups")).toBe(false);
    expect(isSettingsTab("usage")).toBe(false);
    expect(isSettingsTab("audit")).toBe(false);
  });

  it("does not map old registry deep links", () => {
    expect(getSettingsTab("server")).toBe(DEFAULT_SETTINGS_TAB);
    expect(getSettingsTab("storage")).toBe(DEFAULT_SETTINGS_TAB);
    expect(getSettingsTab("vector_store")).toBe(DEFAULT_SETTINGS_TAB);
    expect(getSettingsTab("models")).toBe(DEFAULT_SETTINGS_TAB);
    expect(getSettingsTab("search")).toBe(DEFAULT_SETTINGS_TAB);
    expect(getSettingsTab("chat")).toBe(DEFAULT_SETTINGS_TAB);
  });

  it("finds nav metadata for a tab", () => {
    expect(SETTINGS_NAV_ITEMS.length).toBe(4);
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("backups");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("connectors");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("models");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("usage");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("audit");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("vector_store");
    expect(getSettingsNavItem("backups").value).toBe(DEFAULT_SETTINGS_TAB);
    expect(getSettingsNavItem("unknown").value).toBe(DEFAULT_SETTINGS_TAB);
  });

  it("formats mobile section labels", () => {
    expect(settingsSectionLabel("security")).toBe("Operate / Security");
    expect(settingsSectionLabel("connectors")).toBe("Personal / Account");
    expect(settingsSectionLabel("storage")).toBe("Personal / Account");
  });

  it("groups detailed runtime sections into the data workspace", () => {
    expect(DATA_SETTINGS_GROUPS).toContain("storage");
    expect(DATA_SETTINGS_GROUPS).toContain("retention");
    expect(DATA_SETTINGS_GROUPS).toContain("webhooks");
    expect(DATA_SETTINGS_GROUPS).not.toContain("vector_store");
  });
});
