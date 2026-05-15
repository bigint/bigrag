import { describe, expect, it } from "vitest";
import {
  defaultPresetFormValues,
  embeddingModelOptions,
  presetBodyFromValues,
  selectedEmbeddingDimension,
  validatePresetFormValues,
} from "./preset-form-state";

const editing = {
  base_url: null,
  created_at: "2026-05-15T00:00:00Z",
  dimension: 3072,
  has_api_key: true,
  id: "preset_1",
  model: "text-embedding-3-large",
  name: "Large",
  provider: "openai" as const,
  updated_at: "2026-05-15T00:00:00Z",
};

describe("preset form state", () => {
  it("creates defaults for new and edited presets", () => {
    expect(defaultPresetFormValues(null)).toMatchObject({
      apiKey: "",
      model: "text-embedding-3-small",
      name: "",
      provider: "openai",
    });
    expect(defaultPresetFormValues(editing)).toMatchObject({
      apiKey: "",
      model: editing.model,
      name: editing.name,
      provider: editing.provider,
    });
  });

  it("filters model options by provider", () => {
    expect(
      embeddingModelOptions(
        [
          { provider: "openai", model: "text-embedding-3-small", dimension: 1536 },
          { provider: "voyage", model: "voyage-3.5", dimension: 1024 },
        ],
        "openai",
      ),
    ).toEqual([{ value: "text-embedding-3-small", label: "text-embedding-3-small · 1536d" }]);
  });

  it("resolves dimensions from catalog, edit data, then defaults", () => {
    expect(
      selectedEmbeddingDimension({
        editing,
        model: "text-embedding-3-small",
        models: [{ provider: "openai", model: "text-embedding-3-small", dimension: 1536 }],
        provider: "openai",
      }),
    ).toBe(1536);
    expect(
      selectedEmbeddingDimension({
        editing,
        model: editing.model,
        models: [],
        provider: "openai",
      }),
    ).toBe(3072);
    expect(
      selectedEmbeddingDimension({
        editing: null,
        model: "missing",
        models: [],
        provider: "cohere",
      }),
    ).toBe(1024);
  });

  it("validates and builds preset payloads", () => {
    expect(
      validatePresetFormValues(
        { apiKey: "", model: "text-embedding-3-small", name: "", provider: "openai" },
        null,
      ),
    ).toBe("Name is required");
    expect(
      validatePresetFormValues(
        { apiKey: "", model: "text-embedding-3-small", name: "Small", provider: "openai" },
        null,
      ),
    ).toBe("API key is required");
    expect(
      presetBodyFromValues(
        {
          apiKey: " sk-test ",
          model: " text-embedding-3-small ",
          name: " Small ",
          provider: "openai",
        },
        1536,
      ),
    ).toEqual({
      api_key: "sk-test",
      dimension: 1536,
      model: "text-embedding-3-small",
      name: "Small",
      provider: "openai",
    });
  });
});
