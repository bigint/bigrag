import type { InstanceSettingGroup } from "@/types/bigrag";

export type ModelsTab = "presets" | "settings";

export const MODEL_SETTINGS_GROUPS: readonly InstanceSettingGroup[] = ["search", "chat"];

export const getModelsTab = (requestedTab: string | undefined): ModelsTab =>
  requestedTab === "settings" ? "settings" : "presets";

export const getModelsFocusGroup = (
  requestedGroup: string | undefined,
): InstanceSettingGroup | undefined =>
  requestedGroup === "search" || requestedGroup === "chat" ? requestedGroup : undefined;
