import { describe, expect, it } from "vitest";
import {
  DATA_SETTINGS_GROUPS,
  DEFAULT_SETTINGS_TAB,
  getSettingsFocusGroup,
  getSettingsNavItem,
  getSettingsTab,
  isSettingsTab,
  MODEL_SETTINGS_GROUPS,
  SETTINGS_NAV_ITEMS,
  settingsAliasLabel,
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
    expect(isSettingsTab("server")).toBe(false);
    expect(isSettingsTab("backups")).toBe(false);
    expect(isSettingsTab("usage")).toBe(false);
    expect(isSettingsTab("audit")).toBe(false);
  });

  it("maps old registry deep links into the redesigned areas", () => {
    expect(getSettingsTab("server")).toBe("health");
    expect(getSettingsTab("vector_store")).toBe("data");
    expect(getSettingsTab("chat")).toBe("models");
    expect(getSettingsFocusGroup("vector_store")).toBe("vector_store");
    expect(getSettingsFocusGroup("chat")).toBe("chat");
  });

  it("finds nav metadata for a tab", () => {
    expect(SETTINGS_NAV_ITEMS.length).toBe(6);
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("backups");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("usage");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("audit");
    expect(getSettingsNavItem("backups").value).toBe(DEFAULT_SETTINGS_TAB);
    expect(getSettingsNavItem("unknown").value).toBe(DEFAULT_SETTINGS_TAB);
  });

  it("formats mobile section labels", () => {
    expect(settingsSectionLabel("security")).toBe("Operate / Security");
    expect(settingsSectionLabel("connectors")).toBe("Integrate / Connectors");
    expect(settingsAliasLabel("vector_store")).toBe("Vector store");
  });

  it("groups detailed runtime sections into data and model workspaces", () => {
    expect(DATA_SETTINGS_GROUPS).toContain("storage");
    expect(DATA_SETTINGS_GROUPS).toContain("retention");
    expect(MODEL_SETTINGS_GROUPS).toEqual(["search", "chat"]);
  });
});
