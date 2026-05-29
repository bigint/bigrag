import { useStore } from "@tanstack/react-form";
import { useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { QueryError } from "@/components/ui/query-error";
import { useInstanceSettingsForm } from "@/features/settings/instance-settings/instance-settings-form";
import { RuntimeSettingsPanel } from "@/features/settings/instance-settings/runtime-settings-panel";
import {
  useSpecsByGroup,
  useTargetGroups,
} from "@/features/settings/instance-settings/use-instance-settings-groups";
import { instanceSettingsFormValues } from "@/features/settings/instance-settings-form-state";
import { valuesForSubmit } from "@/features/settings/instance-settings-helpers";
import type { SettingsGroupLayout } from "@/features/settings/settings-layout";
import {
  useInstanceSettings,
  usePurgeEmbeddingCache,
  useUpdateInstanceSettings,
} from "@/hooks/use-instance-settings";
import type { InstanceSettingGroup } from "@/types/bigrag";

type InstanceSettingsTabProps = {
  readonly focusGroup?: InstanceSettingGroup;
  readonly group?: InstanceSettingGroup;
  readonly groups?: readonly InstanceSettingGroup[];
  readonly includeKeys?: readonly string[];
  readonly layoutOverride?: Partial<
    Pick<
      SettingsGroupLayout,
      "description" | "emptyState" | "eyebrow" | "recommendedAction" | "title"
    >
  >;
  readonly stacked?: boolean;
};

export const InstanceSettingsTab = ({
  focusGroup,
  group,
  groups,
  includeKeys,
  layoutOverride,
  stacked = false,
}: InstanceSettingsTabProps) => {
  const targetGroups = useTargetGroups(group, groups);
  const { data, error, isError, isPending, refetch } = useInstanceSettings();
  const save = useUpdateInstanceSettings();
  const purgeEmbeddingCache = usePurgeEmbeddingCache();
  const form = useInstanceSettingsForm();
  const draft = useStore(form.store, (state) => state.values);
  const specsByGroup = useSpecsByGroup(data, targetGroups, includeKeys);
  const isBusy = isPending || save.isPending;
  const [purgeOpen, setPurgeOpen] = useState(false);

  useEffect(() => {
    if (!data) return;
    form.reset(instanceSettingsFormValues(data, targetGroups));
  }, [data, form, targetGroups]);

  if (isPending) {
    return (
      <section className="rounded-md border border-border bg-card px-4 py-10 text-center text-sm text-muted-foreground">
        Loading settings...
      </section>
    );
  }

  if (isError) {
    return (
      <QueryError error={error} onRetry={() => refetch()} title="Runtime settings could not load" />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {targetGroups.map((targetGroup, index) => {
        const specs = specsByGroup[targetGroup] ?? [];
        return (
          <RuntimeSettingsPanel
            collapsible={targetGroups.length > 1}
            defaultOpen={
              targetGroups.length === 1 ||
              focusGroup === targetGroup ||
              (!focusGroup && index === 0)
            }
            form={form}
            group={targetGroup}
            isBusy={isBusy}
            isFocused={focusGroup === targetGroup}
            layoutOverride={layoutOverride}
            key={targetGroup}
            onPurgeEmbeddingCache={() => setPurgeOpen(true)}
            onSave={() =>
              save.mutate({ values: valuesForSubmit(specs, draft, data?.values ?? {}) })
            }
            purgePending={purgeEmbeddingCache.isPending}
            settingValues={data?.values ?? {}}
            specs={specs}
            stacked={stacked}
          />
        );
      })}
      <ConfirmDialog
        open={purgeOpen}
        onClose={() => setPurgeOpen(false)}
        onConfirm={() => {
          purgeEmbeddingCache.mutate(undefined, {
            onSettled: () => setPurgeOpen(false),
          });
        }}
        title="Purge embedding cache"
        description="Purge every persistent embedding cache row? Future ingestion will request fresh embeddings and pay the provider cost again."
        confirmLabel="Purge"
        loading={purgeEmbeddingCache.isPending}
      />
    </div>
  );
};
