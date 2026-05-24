import { useEffect, useState } from "react";
import { Empty } from "@/components/ui/empty";
import { AdvancedSettings } from "@/features/settings/instance-settings/advanced-settings";
import type { InstanceSettingsForm } from "@/features/settings/instance-settings/instance-settings-form";
import { PanelActions } from "@/features/settings/instance-settings/panel-actions";
import { CollapsedPanel, PanelHeader } from "@/features/settings/instance-settings/panel-header";
import { SettingField } from "@/features/settings/instance-settings/setting-field";
import {
  getSettingsGroupLayout,
  type SettingsGroupLayout,
  settingsStatusSummary,
  splitSettingsByImportance,
} from "@/features/settings/settings-layout";
import { cn } from "@/lib/cn";
import type {
  InstanceSettingGroup,
  InstanceSettingSpec,
  InstanceSettingValue,
} from "@/types/bigrag";

export const RuntimeSettingsPanel = ({
  collapsible,
  defaultOpen,
  form,
  group,
  isBusy,
  isFocused,
  layoutOverride,
  onPurgeEmbeddingCache,
  onSave,
  purgePending,
  settingValues,
  specs,
  stacked,
}: {
  readonly collapsible: boolean;
  readonly defaultOpen: boolean;
  readonly form: InstanceSettingsForm;
  readonly group: InstanceSettingGroup;
  readonly isBusy: boolean;
  readonly isFocused: boolean;
  readonly layoutOverride?: Partial<
    Pick<
      SettingsGroupLayout,
      "description" | "emptyState" | "eyebrow" | "recommendedAction" | "title"
    >
  >;
  readonly onPurgeEmbeddingCache: () => void;
  readonly onSave: () => void;
  readonly purgePending: boolean;
  readonly settingValues: Readonly<Record<string, InstanceSettingValue | undefined>>;
  readonly specs: readonly InstanceSettingSpec[];
  readonly stacked: boolean;
}) => {
  const layout = { ...getSettingsGroupLayout(group), ...layoutOverride };
  const { advanced, common } = splitSettingsByImportance(specs, layout);
  const summary = settingsStatusSummary(specs, settingValues, layout);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [open, setOpen] = useState(defaultOpen);
  const hasSettings = specs.length > 0;

  useEffect(() => {
    if (isFocused) setOpen(true);
  }, [isFocused]);

  return (
    <section
      className={cn(
        "overflow-hidden rounded-md border bg-card",
        isFocused ? "border-foreground" : "border-border",
      )}
    >
      <PanelHeader
        collapsible={collapsible}
        layout={layout}
        onOpenChange={setOpen}
        open={open}
        summary={summary}
      />
      {open ? (
        <div>
          <div className="min-w-0">
            {hasSettings ? (
              <>
                <div className="divide-y divide-border">
                  {common.map((spec) => (
                    <SettingField
                      form={form}
                      key={spec.key}
                      setting={settingValues[spec.key]}
                      spec={spec}
                      stacked={stacked}
                    />
                  ))}
                </div>
                {advanced.length > 0 && (
                  <AdvancedSettings
                    dangerKeys={layout.dangerKeys ?? []}
                    form={form}
                    onOpenChange={setAdvancedOpen}
                    open={advancedOpen}
                    settingValues={settingValues}
                    specs={advanced}
                    stacked={stacked}
                  />
                )}
              </>
            ) : (
              <Empty
                bordered={false}
                className="m-4 rounded-md border border-dashed border-border bg-muted/35"
                description={layout.emptyState}
                title="No controls available"
              />
            )}
          </div>
          <PanelActions
            disabled={!hasSettings || isBusy}
            group={group}
            layout={layout}
            onPurgeEmbeddingCache={onPurgeEmbeddingCache}
            onSave={onSave}
            purgePending={purgePending}
            summary={summary}
            stacked={stacked}
          />
        </div>
      ) : (
        <CollapsedPanel layout={layout} summary={summary} />
      )}
    </section>
  );
};
