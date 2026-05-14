import { describe, expect, it } from "vitest";
import type { InstanceSettingSpec, InstanceSettingValue } from "@/types/bigrag";
import {
  getSettingsGroupLayout,
  settingsRecommendedAction,
  settingsStatusSummary,
  splitSettingsByImportance,
} from "./settings-layout";

const spec = (overrides: Partial<InstanceSettingSpec>): InstanceSettingSpec => ({
  default: "",
  description: "Base description.",
  group: "security",
  key: "base",
  kind: "string",
  label: "Base",
  max: null,
  min: null,
  options: [],
  restart_required: false,
  secret: false,
  ...overrides,
});

const value = (overrides: Partial<InstanceSettingValue>): InstanceSettingValue => ({
  has_value: true,
  key: "base",
  source: "database",
  updated_at: null,
  updated_by: null,
  value: "saved",
  ...overrides,
});

describe("settings layout", () => {
  it("splits settings into common and advanced controls", () => {
    const layout = getSettingsGroupLayout("security");
    const result = splitSettingsByImportance(
      [spec({ key: "cors_origins" }), spec({ key: "trusted_proxies", restart_required: true })],
      layout,
    );

    expect(result.common.map((item) => item.key)).toEqual(["cors_origins"]);
    expect(result.advanced.map((item) => item.key)).toEqual(["trusted_proxies"]);
  });

  it("summarizes overrides, secrets, and restart-bound settings", () => {
    const layout = getSettingsGroupLayout("storage");
    const specs = [
      spec({ group: "storage", key: "storage_backend", restart_required: true }),
      spec({
        group: "storage",
        key: "storage_s3_secret_access_key",
        kind: "secret",
        restart_required: true,
        secret: true,
      }),
    ];

    const summary = settingsStatusSummary(
      specs,
      {
        storage_backend: value({ key: "storage_backend" }),
        storage_s3_secret_access_key: value({
          has_value: false,
          key: "storage_s3_secret_access_key",
          source: "default",
        }),
      },
      layout,
    );

    expect(summary).toMatchObject({
      common: 2,
      missingSecrets: 1,
      overrides: 1,
      restartBound: 2,
      secrets: 1,
      total: 2,
    });
  });

  it("uses credential guidance before generic group guidance", () => {
    const layout = getSettingsGroupLayout("backups");
    expect(
      settingsRecommendedAction(layout, {
        advanced: 1,
        common: 6,
        missingSecrets: 1,
        overrides: 0,
        restartBound: 0,
        secrets: 2,
        total: 7,
      }),
    ).toBe("Add the missing credentials, save, then test the connection.");
  });
});
