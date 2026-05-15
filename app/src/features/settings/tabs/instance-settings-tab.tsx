import { useForm, useStore } from "@tanstack/react-form";
import { ChevronDown, ChevronRight, Save, Trash2 } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  groupSpecs,
  type InstanceSettingsFormValues,
  instanceSettingsFormValues,
} from "@/features/settings/instance-settings-form-state";
import {
  type DraftValue,
  inputType,
  settingDescription,
  valuesForSubmit,
} from "@/features/settings/instance-settings-helpers";
import {
  getSettingsGroupLayout,
  type SettingsGroupLayout,
  type SettingsStatusSummary,
  settingsRecommendedAction,
  settingsStatusSummary,
  splitSettingsByImportance,
} from "@/features/settings/settings-layout";
import {
  useInstanceSettings,
  usePurgeEmbeddingCache,
  useUpdateInstanceSettings,
} from "@/hooks/use-instance-settings";
import { cn } from "@/lib/cn";
import type {
  InstanceSettingGroup,
  InstanceSettingSpec,
  InstanceSettingsResponse,
  InstanceSettingValue,
} from "@/types/bigrag";

type InstanceSettingsTabProps = {
  readonly focusGroup?: InstanceSettingGroup;
  readonly group?: InstanceSettingGroup;
  readonly groups?: readonly InstanceSettingGroup[];
};

const useInstanceSettingsForm = () =>
  useForm({
    defaultValues: {} as InstanceSettingsFormValues,
  });

type InstanceSettingsForm = ReturnType<typeof useInstanceSettingsForm>;

export const InstanceSettingsTab = ({ focusGroup, group, groups }: InstanceSettingsTabProps) => {
  const targetGroups = useTargetGroups(group, groups);
  const { data, isPending } = useInstanceSettings();
  const save = useUpdateInstanceSettings();
  const purgeEmbeddingCache = usePurgeEmbeddingCache();
  const form = useInstanceSettingsForm();
  const draft = useStore(form.store, (state) => state.values);
  const specsByGroup = useSpecsByGroup(data, targetGroups);
  const isBusy = isPending || save.isPending;

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
            key={targetGroup}
            onPurgeEmbeddingCache={() => {
              if (window.confirm("Purge every persistent embedding cache row?")) {
                purgeEmbeddingCache.mutate();
              }
            }}
            onSave={() => save.mutate({ values: valuesForSubmit(specs, draft) })}
            purgePending={purgeEmbeddingCache.isPending}
            settingValues={data?.values ?? {}}
            specs={specs}
          />
        );
      })}
    </div>
  );
};

const useTargetGroups = (
  group: InstanceSettingGroup | undefined,
  groups: readonly InstanceSettingGroup[] | undefined,
) =>
  useMemo(() => {
    if (groups?.length) return groups;
    return group ? [group] : [];
  }, [group, groups]);

const useSpecsByGroup = (
  data: InstanceSettingsResponse | undefined,
  groups: readonly InstanceSettingGroup[],
) => useMemo(() => groupSpecs(data, groups), [data, groups]);

const RuntimeSettingsPanel = ({
  collapsible,
  defaultOpen,
  form,
  group,
  isBusy,
  isFocused,
  onPurgeEmbeddingCache,
  onSave,
  purgePending,
  settingValues,
  specs,
}: {
  readonly collapsible: boolean;
  readonly defaultOpen: boolean;
  readonly form: InstanceSettingsForm;
  readonly group: InstanceSettingGroup;
  readonly isBusy: boolean;
  readonly isFocused: boolean;
  readonly onPurgeEmbeddingCache: () => void;
  readonly onSave: () => void;
  readonly purgePending: boolean;
  readonly settingValues: Readonly<Record<string, InstanceSettingValue | undefined>>;
  readonly specs: readonly InstanceSettingSpec[];
}) => {
  const layout = getSettingsGroupLayout(group);
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
        <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0 border-border border-b xl:border-r xl:border-b-0">
            {hasSettings ? (
              <>
                <div className="divide-y divide-border">
                  {common.map((spec) => (
                    <SettingField
                      form={form}
                      key={spec.key}
                      setting={settingValues[spec.key]}
                      spec={spec}
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
          />
        </div>
      ) : (
        <CollapsedPanel layout={layout} onOpen={() => setOpen(true)} summary={summary} />
      )}
    </section>
  );
};

const PanelHeader = ({
  collapsible,
  layout,
  onOpenChange,
  open,
  summary,
}: {
  readonly collapsible: boolean;
  readonly layout: SettingsGroupLayout;
  readonly onOpenChange: (open: boolean) => void;
  readonly open: boolean;
  readonly summary: SettingsStatusSummary;
}) => (
  <header className="border-border border-b bg-muted/25 px-4 py-4">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {layout.eyebrow}
        </div>
        <h3 className="mt-1 text-base font-semibold tracking-normal">{layout.title}</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
          {layout.description}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <StatusMetric label="Common" value={summary.common} />
        <StatusMetric label="Advanced" value={summary.advanced} />
        <StatusMetric label="Overrides" value={summary.overrides} />
        {collapsible && (
          <button
            aria-expanded={open}
            className="inline-flex min-w-20 items-center justify-center gap-1.5 rounded-md border border-border bg-background px-3 py-2 text-xs font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => onOpenChange(!open)}
            type="button"
          >
            {open ? "Close" : "Open"}
            {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          </button>
        )}
      </div>
    </div>
  </header>
);

const CollapsedPanel = ({
  layout,
  onOpen,
  summary,
}: {
  readonly layout: SettingsGroupLayout;
  readonly onOpen: () => void;
  readonly summary: SettingsStatusSummary;
}) => (
  <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
    <p className="max-w-3xl text-sm text-muted-foreground">
      {settingsRecommendedAction(layout, summary)}
    </p>
    <Button onClick={onOpen} variant="outline">
      <ChevronRight className="size-3.5" />
      Open controls
    </Button>
  </div>
);

const StatusMetric = ({ label, value }: { readonly label: string; readonly value: number }) => (
  <div className="min-w-20 rounded-md border border-border bg-background px-3 py-2 text-center">
    <div className="text-sm font-semibold">{value}</div>
    <div className="mt-0.5 text-[11px] text-muted-foreground">{label}</div>
  </div>
);

const PanelActions = ({
  disabled,
  group,
  layout,
  onPurgeEmbeddingCache,
  onSave,
  purgePending,
  summary,
}: {
  readonly disabled: boolean;
  readonly group: InstanceSettingGroup;
  readonly layout: SettingsGroupLayout;
  readonly onPurgeEmbeddingCache: () => void;
  readonly onSave: () => void;
  readonly purgePending: boolean;
  readonly summary: SettingsStatusSummary;
}) => (
  <aside className="flex flex-col gap-4 bg-background p-4">
    <div className="rounded-md border border-border bg-card p-3">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Next action
      </div>
      <p className="mt-2 text-sm leading-5">{settingsRecommendedAction(layout, summary)}</p>
    </div>
    <div className="grid gap-2">
      <Button disabled={disabled} onClick={onSave}>
        <Save className="size-3.5" />
        Save
      </Button>
    </div>
    <div className="flex flex-wrap gap-1.5">
      {summary.secrets > 0 && <Badge variant="neutral">{summary.secrets} secrets</Badge>}
      {summary.missingSecrets > 0 && (
        <Badge variant="warning">{summary.missingSecrets} empty</Badge>
      )}
    </div>
    {group === "security" && (
      <Button disabled={purgePending} onClick={onPurgeEmbeddingCache} variant="destructive">
        <Trash2 className="size-3.5" />
        Purge embedding cache
      </Button>
    )}
  </aside>
);

const AdvancedSettings = ({
  dangerKeys,
  form,
  onOpenChange,
  open,
  settingValues,
  specs,
}: {
  readonly dangerKeys: readonly string[];
  readonly form: InstanceSettingsForm;
  readonly onOpenChange: (open: boolean) => void;
  readonly open: boolean;
  readonly settingValues: Readonly<Record<string, InstanceSettingValue | undefined>>;
  readonly specs: readonly InstanceSettingSpec[];
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
          />
        ))}
      </div>
    )}
  </div>
);

const SettingField = ({
  danger = false,
  form,
  setting,
  showMetadata = false,
  spec,
}: {
  readonly danger?: boolean;
  readonly form: InstanceSettingsForm;
  readonly setting?: InstanceSettingValue;
  readonly showMetadata?: boolean;
  readonly spec: InstanceSettingSpec;
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
        >
          <SettingControl
            field={{
              onBlur: field.handleBlur,
              onChange: field.handleChange,
              value: field.state.value,
            }}
            setting={setting}
            spec={spec}
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
}: {
  readonly field: {
    readonly onBlur: () => void;
    readonly onChange: (value: DraftValue) => void;
    readonly value: DraftValue | undefined;
  };
  readonly setting?: InstanceSettingValue;
  readonly spec: InstanceSettingSpec;
}) => {
  if (spec.kind === "bool") {
    return (
      <div className="flex min-h-10 items-center justify-end">
        <Switch
          aria-label={spec.label}
          checked={Boolean(field.value)}
          onCheckedChange={field.onChange}
        />
      </div>
    );
  }
  if (spec.kind === "select") {
    return (
      <Select
        aria-label={spec.label}
        onChange={field.onChange}
        options={spec.options.map((option) => ({ label: option, value: option }))}
        value={String(field.value ?? "")}
      />
    );
  }
  if (spec.kind === "string_list" || spec.kind === "int_list") {
    return (
      <Textarea
        aria-label={spec.label}
        className="min-h-20 rounded-md px-3 py-2"
        onBlur={field.onBlur}
        onChange={(event) => field.onChange(event.target.value)}
        value={String(field.value ?? "")}
      />
    );
  }
  return (
    <Input
      aria-label={spec.label}
      onBlur={field.onBlur}
      onChange={(event) => field.onChange(event.target.value)}
      placeholder={spec.secret && setting?.has_value ? "Saved" : undefined}
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
}: {
  readonly children: ReactNode;
  readonly danger: boolean;
  readonly description: string;
  readonly setting?: InstanceSettingValue;
  readonly showMetadata: boolean;
  readonly spec: InstanceSettingSpec;
}) => (
  <div
    className={cn(
      "grid gap-3 px-4 py-3 lg:grid-cols-[minmax(0,1fr)_minmax(260px,420px)] lg:items-start",
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
