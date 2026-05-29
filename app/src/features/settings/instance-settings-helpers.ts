import { match } from "ts-pattern";
import type { InstanceSettingSpec, InstanceSettingValue } from "@/types/bigrag";

export type DraftValue = boolean | string;

const examplePlaceholders: Record<string, string> = {
  allowed_chat_base_urls: "https://api.openai.com/v1",
  allowed_embedding_base_urls: "https://api.openai.com/v1",
  chat_base_url: "https://api.openai.com/v1",
  embedding_api_key: "Paste API key",
  embedding_base_url: "https://api.openai.com/v1",
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

export type SettingControlKind = "bool" | "select" | "turbopuffer_region" | "textarea" | "input";

export const settingControlKind = (spec: InstanceSettingSpec): SettingControlKind => {
  if (spec.kind === "bool") return "bool";
  if (spec.kind === "select") return "select";
  if (spec.key === "turbopuffer_region") return "turbopuffer_region";
  if (spec.kind === "string_list" || spec.kind === "int_list") return "textarea";
  return "input";
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
  settingValues: Readonly<Record<string, InstanceSettingValue | undefined>>,
): Record<string, unknown> => {
  const values: Record<string, unknown> = {};
  for (const spec of specs) {
    const value = draft[spec.key];
    if (spec.kind === "secret" && !value) continue;
    if (spec.kind !== "secret" && value === draftValue(spec, settingValues[spec.key])) continue;
    values[spec.key] = valueForSubmit(spec, value);
  }
  return values;
};

const valueForSubmit = (spec: InstanceSettingSpec, value: DraftValue): unknown =>
  match(spec.kind)
    .with("int", () => (value === "" ? null : Number.parseInt(String(value), 10)))
    .with("float", () => (value === "" ? null : Number.parseFloat(String(value))))
    .with("int_list", () =>
      String(value)
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean)
        .map((item) => Number.parseInt(item, 10)),
    )
    .with("string_list", () =>
      String(value)
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean),
    )
    .otherwise(() => value);
