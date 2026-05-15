import type { InstanceSettingSpec, InstanceSettingValue } from "@/types/bigrag";

export type DraftValue = boolean | string;

const examplePlaceholders: Record<string, string> = {
  allowed_chat_base_urls: "https://api.openai.com/v1",
  allowed_embedding_base_urls: "https://api.openai.com/v1",
  backup_s3_access_key_id: "Access key ID",
  backup_s3_bucket: "bigrag-backups",
  backup_s3_endpoint_url: "https://account-id.r2.cloudflarestorage.com",
  backup_s3_prefix: "backups/",
  backup_s3_secret_access_key: "Secret access key",
  chat_base_url: "https://api.openai.com/v1",
  cors_origins: "https://app.example.com",
  embedding_api_key: "Paste API key",
  embedding_base_url: "https://api.openai.com/v1",
  qdrant_search_ef: "Optional, e.g. 128",
  session_cookie_domain: ".example.com",
  storage_s3_access_key_id: "Access key ID",
  storage_s3_bucket: "bigrag-documents",
  storage_s3_endpoint_url: "https://account-id.r2.cloudflarestorage.com",
  storage_s3_prefix: "documents/",
  storage_s3_secret_access_key: "Secret access key",
  trusted_proxies: "10.0.0.0/8",
  turbopuffer_api_key: "Paste turbopuffer API key",
};

const defaultPlaceholder = (value: unknown): string | undefined => {
  if (Array.isArray(value)) {
    return value.length ? `Default:\n${value.join("\n")}` : undefined;
  }
  if (typeof value === "number") return `Default: ${value}`;
  if (typeof value === "string" && value.trim()) return `Default: ${value}`;
  return undefined;
};

const numericPlaceholder = (spec: InstanceSettingSpec): string => {
  if (spec.min !== null && spec.max !== null) return `Range: ${spec.min}-${spec.max}`;
  if (spec.min !== null) return `Min: ${spec.min}`;
  if (spec.max !== null) return `Max: ${spec.max}`;
  return "Enter a number";
};

const stringPlaceholder = (spec: InstanceSettingSpec): string => {
  const label = spec.label.toLowerCase();
  if (spec.key.endsWith("_url") || label.includes("url")) return "https://example.com";
  if (spec.key.endsWith("_domain") || label.includes("domain")) return "example.com";
  return `Enter ${label}`;
};

export const settingDescription = (
  spec: InstanceSettingSpec,
  setting?: InstanceSettingValue,
): string => {
  if (spec.secret && setting?.has_value) {
    return `${spec.description} Leave blank to keep the saved value.`;
  }
  return spec.description;
};

export const settingPlaceholder = (
  spec: InstanceSettingSpec,
  setting?: InstanceSettingValue,
): string | undefined => {
  if (spec.kind === "bool") return undefined;
  if (spec.kind === "secret" && setting?.has_value) return "Saved";
  if (examplePlaceholders[spec.key]) return examplePlaceholders[spec.key];
  const defaultText = defaultPlaceholder(spec.default);
  if (defaultText) return defaultText;
  if (spec.kind === "string_list" || spec.kind === "int_list") return "One value per line";
  if (spec.kind === "int" || spec.kind === "float") return numericPlaceholder(spec);
  if (spec.kind === "secret") return "Paste secret";
  if (spec.kind === "string") return stringPlaceholder(spec);
  return undefined;
};

export const inputType = (spec: InstanceSettingSpec): "number" | "password" | "text" => {
  if (spec.kind === "int" || spec.kind === "float") return "number";
  if (spec.kind === "secret") return "password";
  return "text";
};

export const draftValue = (
  spec: InstanceSettingSpec,
  setting?: InstanceSettingValue,
): DraftValue => {
  if (spec.kind === "bool") return Boolean(setting?.value ?? spec.default ?? false);
  if (spec.kind === "secret") return "";
  const value = setting?.value ?? spec.default;
  if (Array.isArray(value)) return value.join("\n");
  return value === null || value === undefined ? "" : String(value);
};

export const valuesForSubmit = (
  specs: readonly InstanceSettingSpec[],
  draft: Readonly<Record<string, DraftValue>>,
): Record<string, unknown> => {
  const values: Record<string, unknown> = {};
  for (const spec of specs) {
    const value = draft[spec.key];
    if (spec.kind === "secret" && !value) continue;
    values[spec.key] = value;
  }
  return values;
};
