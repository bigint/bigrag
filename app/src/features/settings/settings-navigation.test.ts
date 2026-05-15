import { describe, expect, it } from "vitest";
import {
  DATA_SETTINGS_GROUPS,
  getSettingsTab,
  SECURITY_SETTINGS_KEYS,
  SETTINGS_NAV_ITEMS,
} from "./settings-navigation";

describe("settings navigation", () => {
  it("falls back to the default tab for empty or unknown input", () => {
    expect(getSettingsTab(undefined)).toBe("account");
    expect(getSettingsTab("missing")).toBe("account");
  });

  it("accepts valid settings tabs", () => {
    expect(getSettingsTab("security")).toBe("security");
    expect(getSettingsTab("server")).toBe("account");
    expect(getSettingsTab("models")).toBe("account");
    expect(getSettingsTab("connectors")).toBe("account");
    expect(getSettingsTab("backups")).toBe("account");
    expect(getSettingsTab("usage")).toBe("account");
    expect(getSettingsTab("audit")).toBe("account");
  });

  it("does not map old registry deep links", () => {
    expect(getSettingsTab("server")).toBe("account");
    expect(getSettingsTab("storage")).toBe("account");
    expect(getSettingsTab("vector_store")).toBe("account");
    expect(getSettingsTab("models")).toBe("account");
    expect(getSettingsTab("search")).toBe("account");
    expect(getSettingsTab("chat")).toBe("account");
  });

  it("finds nav metadata for a tab", () => {
    expect(SETTINGS_NAV_ITEMS.length).toBe(4);
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("backups");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("connectors");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("models");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("usage");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("audit");
    expect(SETTINGS_NAV_ITEMS.map((item) => item.value)).not.toContain("vector_store");
    expect(getSettingsTab("backups")).toBe("account");
    expect(getSettingsTab("unknown")).toBe("account");
  });

  it("groups detailed runtime sections into the data workspace", () => {
    expect(DATA_SETTINGS_GROUPS).toContain("storage");
    expect(DATA_SETTINGS_GROUPS).toContain("retention");
    expect(DATA_SETTINGS_GROUPS).toContain("webhooks");
    expect(DATA_SETTINGS_GROUPS).not.toContain("vector_store");
  });

  it("keeps browser deployment controls out of the security tab", () => {
    expect(SECURITY_SETTINGS_KEYS).toContain("trusted_proxies");
    expect(SECURITY_SETTINGS_KEYS).toContain("embedding_cache_mode");
    expect(SECURITY_SETTINGS_KEYS).not.toContain("cors_origins");
    expect(SECURITY_SETTINGS_KEYS).not.toContain("session_cookie_secure");
    expect(SECURITY_SETTINGS_KEYS).not.toContain("session_cookie_samesite");
    expect(SECURITY_SETTINGS_KEYS).not.toContain("session_cookie_domain");
  });
});
