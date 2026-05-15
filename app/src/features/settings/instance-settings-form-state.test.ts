import { describe, expect, it } from "vitest";
import { groupSpecs, instanceSettingsFormValues } from "./instance-settings-form-state";

const settings = {
  specs: [
    {
      default: false,
      description: "Secure cookie flag.",
      group: "security" as const,
      key: "session_cookie_secure",
      kind: "bool" as const,
      label: "Secure cookies",
      max: null,
      min: null,
      options: [],
      secret: false,
    },
    {
      default: "qdrant",
      description: "Vector provider.",
      group: "vector_store" as const,
      key: "vector_store_provider",
      kind: "select" as const,
      label: "Vector provider",
      max: null,
      min: null,
      options: ["qdrant", "turbopuffer"],
      secret: false,
    },
  ],
  values: {
    session_cookie_secure: {
      has_value: true,
      key: "session_cookie_secure",
      source: "database" as const,
      updated_at: null,
      updated_by: null,
      value: true,
    },
    vector_store_provider: {
      has_value: true,
      key: "vector_store_provider",
      source: "database" as const,
      updated_at: null,
      updated_by: null,
      value: "turbopuffer",
    },
  },
};

describe("instance settings form state", () => {
  it("builds form values for the selected groups", () => {
    expect(instanceSettingsFormValues(settings, ["security"])).toEqual({
      session_cookie_secure: true,
    });
  });

  it("groups specs for settings panels", () => {
    expect(groupSpecs(settings, ["security", "vector_store"])).toMatchObject({
      security: [settings.specs[0]],
      vector_store: [settings.specs[1]],
    });
  });
});
