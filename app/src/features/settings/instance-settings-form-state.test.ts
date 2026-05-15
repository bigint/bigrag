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
      default: "http://localhost:6333",
      description: "Qdrant URL.",
      group: "vector_store" as const,
      key: "qdrant_url",
      kind: "string" as const,
      label: "Qdrant URL",
      max: null,
      min: null,
      options: [],
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
    qdrant_url: {
      has_value: true,
      key: "qdrant_url",
      source: "database" as const,
      updated_at: null,
      updated_by: null,
      value: "http://qdrant:6333",
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
