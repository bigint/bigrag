import { describe, expect, it } from "vitest";
import {
  getLegacyModelSettingsSearch,
  getModelsFocusGroup,
  getModelsTab,
  MODEL_SETTINGS_GROUPS,
} from "./model-tabs";

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

  it("maps legacy settings links into model settings search", () => {
    expect(getLegacyModelSettingsSearch("models")).toEqual({ tab: "settings" });
    expect(getLegacyModelSettingsSearch("search")).toEqual({ tab: "settings", group: "search" });
    expect(getLegacyModelSettingsSearch("chat")).toEqual({ tab: "settings", group: "chat" });
    expect(getLegacyModelSettingsSearch("storage")).toBeNull();
  });
});
