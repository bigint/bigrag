import type { InstanceSettingSpec, InstanceSettingValue } from "@/types/bigrag";

export type DraftValue = boolean | string;

export const settingDescription = (
  spec: InstanceSettingSpec,
  setting?: InstanceSettingValue,
): string => {
  if (spec.secret && setting?.has_value) {
    return `${spec.description} Leave blank to keep the saved value.`;
  }
  return spec.description;
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
