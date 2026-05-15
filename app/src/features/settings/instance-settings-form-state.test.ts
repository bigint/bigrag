import { describe, expect, it } from "vitest";
import { groupSpecs, instanceSettingsFormValues } from "./instance-settings-form-state";

const settings = {
  specs: [
    {
      default: "encrypted",
      description: "Persistent cache behavior.",
      group: "security" as const,
      key: "embedding_cache_mode",
      kind: "select" as const,
      label: "Embedding cache mode",
      max: null,
      min: null,
      options: ["encrypted", "disabled"],
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
    embedding_cache_mode: {
      has_value: true,
      key: "embedding_cache_mode",
      source: "database" as const,
      updated_at: null,
      updated_by: null,
      value: "encrypted",
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
      embedding_cache_mode: "encrypted",
    });
  });

  it("groups specs for settings panels", () => {
    expect(groupSpecs(settings, ["security", "vector_store"])).toMatchObject({
      security: [settings.specs[0]],
      vector_store: [settings.specs[1]],
    });
  });
});
