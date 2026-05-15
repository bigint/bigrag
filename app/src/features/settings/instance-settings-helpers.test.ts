import { describe, expect, it } from "vitest";
import type { InstanceSettingSpec, InstanceSettingValue } from "@/types/bigrag";
import {
  draftValue,
  inputType,
  settingDescription,
  settingPlaceholder,
  valuesForSubmit,
} from "./instance-settings-helpers";

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

describe("instance settings helpers", () => {
  it("formats draft values from settings and defaults", () => {
    expect(draftValue(spec({ kind: "bool" }), value({ value: true }))).toBe(true);
    expect(draftValue(spec({ default: ["a", "b"], kind: "string_list" }))).toBe("a\nb");
    expect(draftValue(spec({ default: 12, kind: "int" }))).toBe("12");
    expect(draftValue(spec({ kind: "secret" }), value({ value: "hidden" }))).toBe("");
  });

  it("omits empty secrets when submitting", () => {
    const specs = [
      spec({ key: "public", kind: "string" }),
      spec({ key: "secret", kind: "secret", secret: true }),
    ];

    expect(valuesForSubmit(specs, { public: "saved", secret: "" })).toEqual({
      public: "saved",
    });
    expect(valuesForSubmit(specs, { public: "saved", secret: "new-secret" })).toEqual({
      public: "saved",
      secret: "new-secret",
    });
  });

  it("adds saved-secret guidance without changing normal descriptions", () => {
    const secret = spec({ description: "Provider token.", kind: "secret", secret: true });

    expect(settingDescription(secret, value({ has_value: true }))).toBe(
      "Provider token. Leave blank to keep the saved value.",
    );
    expect(settingDescription(secret, value({ has_value: false }))).toBe("Provider token.");
  });

  it("selects input types from setting kind", () => {
    expect(inputType(spec({ kind: "int" }))).toBe("number");
    expect(inputType(spec({ kind: "float" }))).toBe("number");
    expect(inputType(spec({ kind: "secret" }))).toBe("password");
    expect(inputType(spec({ kind: "string" }))).toBe("text");
  });

  it("creates placeholders from saved secrets, defaults, and examples", () => {
    expect(settingPlaceholder(spec({ default: 90, kind: "int" }))).toBe("Default: 90");
    expect(settingPlaceholder(spec({ default: ["10", "30"], kind: "int_list" }))).toBe(
      "Default:\n10\n30",
    );
    expect(
      settingPlaceholder(
        spec({ kind: "secret", key: "storage_s3_secret_access_key", secret: true }),
        value({ has_value: true }),
      ),
    ).toBe("Saved");
    expect(
      settingPlaceholder(spec({ default: [], kind: "string_list", key: "trusted_proxies" })),
    ).toBe("10.0.0.0/8");
    expect(
      settingPlaceholder(
        spec({ default: null, kind: "int", key: "qdrant_search_ef", max: 10000, min: 1 }),
      ),
    ).toBe("Optional, e.g. 128");
  });
});
