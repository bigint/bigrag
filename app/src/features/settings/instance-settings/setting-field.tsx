import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { InstanceSettingsForm } from "@/features/settings/instance-settings/instance-settings-form";
import {
  type DraftValue,
  inputType,
  settingControlKind,
  settingDescription,
  settingPlaceholder,
} from "@/features/settings/instance-settings-helpers";
import { TURBOPUFFER_REGION_OPTIONS } from "@/features/turbopuffer/region-options";
import { cn } from "@/lib/cn";
import type { InstanceSettingSpec, InstanceSettingValue } from "@/types/bigrag";

export const SettingField = ({
  danger = false,
  form,
  setting,
  showMetadata = false,
  spec,
  stacked = false,
}: {
  readonly danger?: boolean;
  readonly form: InstanceSettingsForm;
  readonly setting?: InstanceSettingValue;
  readonly showMetadata?: boolean;
  readonly spec: InstanceSettingSpec;
  readonly stacked?: boolean;
}) => {
  const description = settingDescription(spec, setting);
  return (
    <form.Field name={spec.key}>
      {(field) => (
        <SettingRow
          danger={danger}
          description={description}
          setting={setting}
          showMetadata={showMetadata}
          spec={spec}
          stacked={stacked}
        >
          <SettingControl
            field={{
              onBlur: field.handleBlur,
              onChange: field.handleChange,
              value: field.state.value,
            }}
            setting={setting}
            spec={spec}
            stacked={stacked}
          />
        </SettingRow>
      )}
    </form.Field>
  );
};

const SettingControl = ({
  field,
  setting,
  spec,
  stacked,
}: {
  readonly field: {
    readonly onBlur: () => void;
    readonly onChange: (value: DraftValue) => void;
    readonly value: DraftValue | undefined;
  };
  readonly setting?: InstanceSettingValue;
  readonly spec: InstanceSettingSpec;
  readonly stacked: boolean;
}) => {
  const placeholder = settingPlaceholder(spec, setting);
  const kind = settingControlKind(spec);
  if (kind === "bool") {
    return (
      <div className={cn("flex min-h-10 items-center", stacked ? "justify-start" : "justify-end")}>
        <Switch
          aria-label={spec.label}
          checked={Boolean(field.value)}
          onCheckedChange={field.onChange}
        />
      </div>
    );
  }
  if (kind === "select") {
    return (
      <Select
        aria-label={spec.label}
        onChange={field.onChange}
        options={spec.options.map((option) => ({ label: option, value: option }))}
        placeholder={placeholder}
        value={String(field.value ?? "")}
      />
    );
  }
  if (kind === "turbopuffer_region") {
    return (
      <Select
        aria-label={spec.label}
        onChange={field.onChange}
        options={TURBOPUFFER_REGION_OPTIONS}
        placeholder={placeholder}
        value={String(field.value ?? "")}
      />
    );
  }
  if (kind === "textarea") {
    return (
      <Textarea
        aria-label={spec.label}
        className="min-h-20 rounded-md px-3 py-2"
        onBlur={field.onBlur}
        onChange={(event) => field.onChange(event.target.value)}
        placeholder={placeholder}
        value={String(field.value ?? "")}
      />
    );
  }
  return (
    <Input
      aria-label={spec.label}
      onBlur={field.onBlur}
      onChange={(event) => field.onChange(event.target.value)}
      placeholder={placeholder}
      type={inputType(spec)}
      value={String(field.value ?? "")}
    />
  );
};

const SettingRow = ({
  children,
  danger,
  description,
  setting,
  showMetadata,
  spec,
  stacked,
}: {
  readonly children: ReactNode;
  readonly danger: boolean;
  readonly description: string;
  readonly setting?: InstanceSettingValue;
  readonly showMetadata: boolean;
  readonly spec: InstanceSettingSpec;
  readonly stacked: boolean;
}) => (
  <div
    className={cn(
      "grid gap-3 px-4 py-3",
      !stacked && "lg:grid-cols-[minmax(0,1fr)_minmax(260px,420px)] lg:items-start",
      danger && "bg-warning/5",
    )}
  >
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-sm font-semibold text-foreground">{spec.label}</div>
        {danger && <Badge variant="warning">sensitive</Badge>}
        {showMetadata && <SettingBadges setting={setting} spec={spec} />}
      </div>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
      {showMetadata && (
        <code className="mt-2 block truncate font-mono text-[11px] text-muted-foreground/80">
          {spec.key}
        </code>
      )}
    </div>
    <div className="min-w-0">{children}</div>
  </div>
);

const SettingBadges = ({
  setting,
  spec,
}: {
  readonly setting?: InstanceSettingValue;
  readonly spec: InstanceSettingSpec;
}) => (
  <div className="flex flex-wrap gap-1.5">
    <Badge variant={setting?.source === "database" ? "primary" : "neutral"}>
      {setting?.source ?? "default"}
    </Badge>
    {spec.secret && <Badge variant="neutral">secret</Badge>}
  </div>
);
