import { describe, expect, it } from "vitest";
import {
  API_KEY_UNSCOPED,
  apiKeyBodyFromValues,
  defaultApiKeyFormValues,
  validateApiKeyFormValues,
} from "./api-key-form-state";

describe("api key form state", () => {
  it("creates defaults and validates names", () => {
    expect(defaultApiKeyFormValues()).toEqual({ collection: API_KEY_UNSCOPED, name: "" });
    expect(validateApiKeyFormValues({ collection: API_KEY_UNSCOPED, name: " " })).toBe(
      "Name is required",
    );
  });

  it("builds scoped and unscoped payloads", () => {
    expect(apiKeyBodyFromValues({ collection: API_KEY_UNSCOPED, name: "Prod" })).toEqual({
      collection: null,
      name: "Prod",
    });
    expect(apiKeyBodyFromValues({ collection: "docs", name: "Docs" })).toEqual({
      collection: "docs",
      name: "Docs",
    });
  });
});
