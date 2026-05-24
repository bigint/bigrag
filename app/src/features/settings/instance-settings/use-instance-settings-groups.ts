import { useMemo } from "react";
import { groupSpecs } from "@/features/settings/instance-settings-form-state";
import type {
  InstanceSettingGroup,
  InstanceSettingSpec,
  InstanceSettingsResponse,
} from "@/types/bigrag";

export const useTargetGroups = (
  group: InstanceSettingGroup | undefined,
  groups: readonly InstanceSettingGroup[] | undefined,
) =>
  useMemo(() => {
    if (groups?.length) return groups;
    return group ? [group] : [];
  }, [group, groups]);

export const useSpecsByGroup = (
  data: InstanceSettingsResponse | undefined,
  groups: readonly InstanceSettingGroup[],
  includeKeys: readonly string[] | undefined,
) =>
  useMemo(() => {
    const grouped = groupSpecs(data, groups);
    if (!includeKeys?.length) return grouped;
    const included = new Set(includeKeys);
    return Object.fromEntries(
      Object.entries(grouped).map(([targetGroup, specs]) => [
        targetGroup,
        specs?.filter((spec) => included.has(spec.key)) ?? [],
      ]),
    ) as Partial<Record<InstanceSettingGroup, InstanceSettingSpec[]>>;
  }, [data, groups, includeKeys]);
