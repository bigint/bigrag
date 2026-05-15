import { type DraftValue, draftValue } from "@/features/settings/instance-settings-helpers";
import type {
  InstanceSettingGroup,
  InstanceSettingSpec,
  InstanceSettingsResponse,
} from "@/types/bigrag";

export type InstanceSettingsFormValues = Record<string, DraftValue>;

export const instanceSettingsFormValues = (
  data: InstanceSettingsResponse,
  groups: readonly InstanceSettingGroup[],
): InstanceSettingsFormValues => {
  const activeGroups = new Set(groups);
  return Object.fromEntries(
    data.specs
      .filter((spec) => activeGroups.has(spec.group))
      .map((spec) => [spec.key, draftValue(spec, data.values[spec.key])]),
  );
};

export const groupSpecs = (
  data: InstanceSettingsResponse | undefined,
  groups: readonly InstanceSettingGroup[],
) => {
  const byGroup = Object.fromEntries(groups.map((targetGroup) => [targetGroup, []])) as Partial<
    Record<InstanceSettingGroup, InstanceSettingSpec[]>
  >;
  for (const spec of data?.specs ?? []) {
    if (groups.includes(spec.group)) {
      byGroup[spec.group] = [...(byGroup[spec.group] ?? []), spec];
    }
  }
  return byGroup;
};
