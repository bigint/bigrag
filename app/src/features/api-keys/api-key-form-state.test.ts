import { describe, expect, it } from "vitest";
import {
  API_KEY_UNSCOPED,
  apiKeyBodyFromValues,
  defaultApiKeyFormValues,
  validateApiKeyFormValues,
} from "./api-key-form-state";

describe("api key form state", () => {
  it("defaults to an unscoped key", () => {
    expect(defaultApiKeyFormValues()).toEqual({
      collection: API_KEY_UNSCOPED,
      name: "",
    });
  });

  it("requires a non-empty name", () => {
    expect(validateApiKeyFormValues({ collection: API_KEY_UNSCOPED, name: " " })).toBe(
      "Name is required",
    );
    expect(validateApiKeyFormValues({ collection: API_KEY_UNSCOPED, name: "CI" })).toBeUndefined();
  });

  it("preserves the create payload shape", () => {
    expect(apiKeyBodyFromValues({ collection: API_KEY_UNSCOPED, name: "CI" })).toEqual({
      collection: null,
      name: "CI",
    });
    expect(apiKeyBodyFromValues({ collection: "docs", name: "Docs" })).toEqual({
      collection: "docs",
      name: "Docs",
    });
  });
});
