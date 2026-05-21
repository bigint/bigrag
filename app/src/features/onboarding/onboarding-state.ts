import type { InstanceSettingsResponse } from "@/types/bigrag";

export type TurbopufferDraft = {
  apiKey: string;
  baseUrl: string;
  namespacePrefix: string;
  region: string;
};

const DEFAULT_TURBOPUFFER_REGION = "aws-us-east-1";
const DEFAULT_TURBOPUFFER_NAMESPACE_PREFIX = "bigrag_";

const settingString = (
  settings: InstanceSettingsResponse | undefined,
  key: string,
  fallback: string,
) => {
  const value = settings?.values[key]?.value;
  return typeof value === "string" ? value : fallback;
};

export const turbopufferDraftFromSettings = (
  settings: InstanceSettingsResponse | undefined,
): TurbopufferDraft => ({
  apiKey: "",
  baseUrl: settingString(settings, "turbopuffer_base_url", ""),
  namespacePrefix: settingString(
    settings,
    "turbopuffer_namespace_prefix",
    DEFAULT_TURBOPUFFER_NAMESPACE_PREFIX,
  ),
  region: settingString(settings, "turbopuffer_region", DEFAULT_TURBOPUFFER_REGION),
});

export const hasTurbopufferApiKey = (settings: InstanceSettingsResponse | undefined) =>
  Boolean(settings?.values.turbopuffer_api_key?.has_value);

export const canSaveTurbopufferDraft = (draft: TurbopufferDraft, hasSavedKey: boolean) =>
  hasSavedKey || Boolean(draft.apiKey.trim());

export const turbopufferSettingsBody = (
  draft: TurbopufferDraft,
  hasSavedKey: boolean,
): Record<string, unknown> => {
  const values: Record<string, unknown> = {
    turbopuffer_base_url: draft.baseUrl.trim() || null,
    turbopuffer_namespace_prefix:
      draft.namespacePrefix.trim() || DEFAULT_TURBOPUFFER_NAMESPACE_PREFIX,
    turbopuffer_region: draft.region.trim() || DEFAULT_TURBOPUFFER_REGION,
  };
  if (!hasSavedKey || draft.apiKey.trim()) {
    values.turbopuffer_api_key = draft.apiKey.trim();
  }
  return values;
};
