import { describe, expect, it } from "vitest";
import {
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
    expect(getSettingsTab("connectors")).toBe("connectors");
    expect(isSettingsTab("security")).toBe(true);
    expect(isSettingsTab("eval")).toBe(false);
  });

  it("finds nav metadata for a tab", () => {
    expect(SETTINGS_NAV_ITEMS.length).toBeGreaterThan(10);
    expect(getSettingsNavItem("backups").label).toBe("Backups");
    expect(getSettingsNavItem("unknown").value).toBe(DEFAULT_SETTINGS_TAB);
  });

  it("formats mobile section labels", () => {
    expect(settingsSectionLabel("security")).toBe("Platform / Security");
    expect(settingsSectionLabel("connectors")).toBe("Runtime / Connectors");
  });
});
