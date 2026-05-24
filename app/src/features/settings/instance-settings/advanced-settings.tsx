import { ChevronDown, ChevronRight } from "lucide-react";
import type { InstanceSettingsForm } from "@/features/settings/instance-settings/instance-settings-form";
import { SettingField } from "@/features/settings/instance-settings/setting-field";
import type { InstanceSettingSpec, InstanceSettingValue } from "@/types/bigrag";

export const AdvancedSettings = ({
  dangerKeys,
  form,
  onOpenChange,
  open,
  settingValues,
  specs,
  stacked,
}: {
  readonly dangerKeys: readonly string[];
  readonly form: InstanceSettingsForm;
  readonly onOpenChange: (open: boolean) => void;
  readonly open: boolean;
  readonly settingValues: Readonly<Record<string, InstanceSettingValue | undefined>>;
  readonly specs: readonly InstanceSettingSpec[];
  readonly stacked: boolean;
}) => (
  <div className="border-border border-t bg-muted/20">
    <button
      aria-expanded={open}
      className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      onClick={() => onOpenChange(!open)}
      type="button"
    >
      <span>Advanced controls</span>
      <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
        {specs.length} settings
        {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
      </span>
    </button>
    {open && (
      <div className="divide-y divide-border border-border border-t bg-card">
        {specs.map((spec) => (
          <SettingField
            danger={dangerKeys.includes(spec.key)}
            form={form}
            key={spec.key}
            setting={settingValues[spec.key]}
            showMetadata
            spec={spec}
            stacked={stacked}
          />
        ))}
      </div>
    )}
  </div>
);
