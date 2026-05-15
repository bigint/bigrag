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
  settingPlaceholder,
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
  readonly includeKeys?: readonly string[];
  readonly layoutOverride?: Partial<
    Pick<
      SettingsGroupLayout,
      "description" | "emptyState" | "eyebrow" | "recommendedAction" | "title"
    >
  >;
  readonly stacked?: boolean;
};

const useInstanceSettingsForm = () =>
  useForm({
    defaultValues: {} as InstanceSettingsFormValues,
  });

type InstanceSettingsForm = ReturnType<typeof useInstanceSettingsForm>;

export const InstanceSettingsTab = ({
  focusGroup,
  group,
  groups,
  includeKeys,
  layoutOverride,
  stacked = false,
}: InstanceSettingsTabProps) => {
  const targetGroups = useTargetGroups(group, groups);
  const { data, isPending } = useInstanceSettings();
  const save = useUpdateInstanceSettings();
  const purgeEmbeddingCache = usePurgeEmbeddingCache();
  const form = useInstanceSettingsForm();
  const draft = useStore(form.store, (state) => state.values);
  const specsByGroup = useSpecsByGroup(data, targetGroups, includeKeys);
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
            layoutOverride={layoutOverride}
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
            stacked={stacked}
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

const RuntimeSettingsPanel = ({
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
  <header className="border-border border-b px-4 py-4">
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
      <div className="flex flex-wrap items-center justify-end gap-2">
        {summary.overrides > 0 && <Badge variant="primary">{summary.overrides} changed</Badge>}
        {summary.missingSecrets > 0 && (
          <Badge variant="warning">{summary.missingSecrets} missing</Badge>
        )}
        {collapsible && (
          <Button
            aria-expanded={open}
            onClick={() => onOpenChange(!open)}
            size="sm"
            type="button"
            variant="outline"
          >
            {open ? "Hide" : "Open"}
            {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          </Button>
        )}
      </div>
    </div>
  </header>
);

const CollapsedPanel = ({
  layout,
  summary,
}: {
  readonly layout: SettingsGroupLayout;
  readonly summary: SettingsStatusSummary;
}) => (
  <div className="px-4 py-3">
    <p className="max-w-3xl text-sm text-muted-foreground">
      {settingsRecommendedAction(layout, summary)}
    </p>
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
  stacked,
}: {
  readonly disabled: boolean;
  readonly group: InstanceSettingGroup;
  readonly layout: SettingsGroupLayout;
  readonly onPurgeEmbeddingCache: () => void;
  readonly onSave: () => void;
  readonly purgePending: boolean;
  readonly summary: SettingsStatusSummary;
  readonly stacked: boolean;
}) => (
  <footer
    className={cn(
      "flex flex-col gap-3 border-border border-t bg-muted/20 px-4 py-3",
      !stacked && "md:flex-row md:items-center md:justify-between",
    )}
  >
    <div className="min-w-0">
      <p className="text-sm leading-5 text-muted-foreground">
        {settingsRecommendedAction(layout, summary)}
      </p>
      {(summary.secrets > 0 || summary.advanced > 0) && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {summary.secrets > 0 && <Badge variant="neutral">{summary.secrets} secrets</Badge>}
          {summary.advanced > 0 && <Badge variant="neutral">{summary.advanced} advanced</Badge>}
        </div>
      )}
    </div>
    <div className={cn("flex shrink-0 flex-wrap gap-2", stacked && "flex-col items-start")}>
      {group === "security" && (
        <Button disabled={purgePending} onClick={onPurgeEmbeddingCache} variant="destructive">
          <Trash2 className="size-3.5" />
          Purge embedding cache
        </Button>
      )}
      <Button disabled={disabled} onClick={onSave}>
        <Save className="size-3.5" />
        Save changes
      </Button>
    </div>
  </footer>
);

const AdvancedSettings = ({
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

const SettingField = ({
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
  if (spec.kind === "bool") {
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
  if (spec.kind === "select") {
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
  if (spec.kind === "string_list" || spec.kind === "int_list") {
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
