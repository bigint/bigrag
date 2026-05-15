import { describe, expect, it } from "vitest";
import { getModelsFocusGroup, getModelsTab, MODEL_SETTINGS_GROUPS } from "./model-tabs";

describe("models tabs", () => {
  it("defaults to embedding presets", () => {
    expect(getModelsTab(undefined)).toBe("presets");
    expect(getModelsTab("missing")).toBe("presets");
    expect(getModelsTab("settings")).toBe("settings");
  });

  it("focuses only runtime model groups", () => {
    expect(MODEL_SETTINGS_GROUPS).toEqual(["search", "chat"]);
    expect(getModelsFocusGroup("search")).toBe("search");
    expect(getModelsFocusGroup("chat")).toBe("chat");
    expect(getModelsFocusGroup("storage")).toBeUndefined();
  });
});
