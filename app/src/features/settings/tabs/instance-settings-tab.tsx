import { RotateCcw, Save, TestTube2, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  type DraftValue,
  draftValue,
  inputType,
  settingDescription,
  valuesForSubmit,
} from "@/features/settings/instance-settings-helpers";
import {
  useInstanceSettings,
  usePurgeEmbeddingCache,
  useResetInstanceSettings,
  useTestInstanceSettings,
  useUpdateInstanceSettings,
} from "@/hooks/use-instance-settings";
import type {
  InstanceSettingGroup,
  InstanceSettingSpec,
  InstanceSettingsResponse,
  InstanceSettingValue,
} from "@/types/bigrag";

export const InstanceSettingsTab = ({ group }: { group: InstanceSettingGroup }) => {
  const { data, isPending } = useInstanceSettings();
  const save = useUpdateInstanceSettings();
  const test = useTestInstanceSettings();
  const reset = useResetInstanceSettings();
  const purgeEmbeddingCache = usePurgeEmbeddingCache();
  const [draft, setDraft] = useInstanceSettingsDraft(data, group);
  const groupSpecs = useMemo(
    () => data?.specs.filter((spec) => spec.group === group) ?? [],
    [data, group],
  );

  const body = () => ({ values: valuesForSubmit(groupSpecs, draft) });
  const restartCount = groupSpecs.filter((spec) => spec.restart_required).length;
  const isBusy = isPending || save.isPending || test.isPending || reset.isPending;

  return (
    <div className="flex flex-col gap-5">
      <section className="overflow-hidden rounded-md border border-border bg-card">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/35 px-4 py-3">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold tracking-normal">Configuration registry</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Database-backed runtime settings for this section.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={restartCount ? "warning" : "success"} dot>
              {restartCount ? `${restartCount} restart-bound` : "applies live"}
            </Badge>
            <Badge variant="neutral" dot>
              {groupSpecs.length} settings
            </Badge>
          </div>
        </header>

        {isPending ? (
          <div className="px-4 py-10 text-center text-sm text-muted-foreground">
            Loading settings…
          </div>
        ) : (
          <div className="divide-y divide-border">
            {groupSpecs.map((spec) => (
              <SettingField
                key={spec.key}
                spec={spec}
                value={draft[spec.key]}
                setting={data?.values[spec.key]}
                onChange={(value) => setDraft((current) => ({ ...current, [spec.key]: value }))}
              />
            ))}
          </div>
        )}
      </section>

      <div className="sticky bottom-0 z-10 rounded-md border border-border bg-background/95 p-3 shadow-sm">
        <SettingsActions
          disabled={!groupSpecs.length || isBusy}
          group={group}
          onPurgeEmbeddingCache={() => {
            if (window.confirm("Purge every persistent embedding cache row?")) {
              purgeEmbeddingCache.mutate();
            }
          }}
          onReset={() => reset.mutate(groupSpecs.map((spec) => spec.key))}
          onSave={() => save.mutate(body())}
          onTest={() => test.mutate(body())}
          purgePending={purgeEmbeddingCache.isPending}
        />
      </div>
    </div>
  );
};

const useInstanceSettingsDraft = (
  data: InstanceSettingsResponse | undefined,
  group: InstanceSettingGroup,
) => {
  const [draft, setDraft] = useState<Record<string, DraftValue>>({});

  useEffect(() => {
    if (!data) return;
    const next: Record<string, DraftValue> = {};
    for (const spec of data.specs.filter((item) => item.group === group)) {
      next[spec.key] = draftValue(spec, data.values[spec.key]);
    }
    setDraft(next);
  }, [data, group]);

  return [draft, setDraft] as const;
};

const SettingField = ({
  spec,
  value,
  setting,
  onChange,
}: {
  spec: InstanceSettingSpec;
  value: DraftValue | undefined;
  setting?: InstanceSettingValue;
  onChange: (value: DraftValue) => void;
}) => {
  const description = settingDescription(spec, setting);
  if (spec.kind === "bool") {
    return (
      <SettingRow spec={spec} setting={setting} description={description}>
        <div className="flex min-h-10 items-center justify-end">
          <Switch aria-label={spec.label} checked={Boolean(value)} onCheckedChange={onChange} />
        </div>
      </SettingRow>
    );
  }
  if (spec.kind === "select") {
    return (
      <SettingRow spec={spec} setting={setting} description={description}>
        <Select
          aria-label={spec.label}
          value={String(value ?? "")}
          onChange={onChange}
          options={spec.options.map((option) => ({ label: option, value: option }))}
        />
      </SettingRow>
    );
  }
  if (spec.kind === "string_list" || spec.kind === "int_list") {
    return (
      <SettingRow spec={spec} setting={setting} description={description}>
        <Textarea
          aria-label={spec.label}
          className="min-h-20 rounded-md px-3 py-2"
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
        />
      </SettingRow>
    );
  }
  return (
    <SettingRow spec={spec} setting={setting} description={description}>
      <Input
        aria-label={spec.label}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        placeholder={spec.secret && setting?.has_value ? "Saved" : undefined}
        type={inputType(spec)}
      />
    </SettingRow>
  );
};

const SettingRow = ({
  children,
  description,
  setting,
  spec,
}: {
  children: React.ReactNode;
  description: string;
  setting?: InstanceSettingValue;
  spec: InstanceSettingSpec;
}) => (
  <div className="grid gap-3 px-4 py-3 lg:grid-cols-[minmax(0,1fr)_minmax(260px,420px)] lg:items-start">
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-sm font-semibold text-foreground">{spec.label}</div>
        <SettingBadges spec={spec} setting={setting} />
      </div>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
      <code className="mt-2 block truncate font-mono text-[11px] text-muted-foreground/80">
        {spec.key}
      </code>
    </div>
    <div className="min-w-0">{children}</div>
  </div>
);

const SettingBadges = ({
  spec,
  setting,
}: {
  spec: InstanceSettingSpec;
  setting?: InstanceSettingValue;
}) => (
  <div className="flex flex-wrap gap-1.5">
    <Badge variant={setting?.source === "database" ? "primary" : "neutral"}>
      {setting?.source ?? "default"}
    </Badge>
    <Badge variant={spec.restart_required ? "warning" : "success"}>
      {spec.restart_required ? "restart" : "live"}
    </Badge>
    {spec.secret && <Badge variant="neutral">secret</Badge>}
  </div>
);

const SettingsActions = ({
  disabled,
  group,
  onPurgeEmbeddingCache,
  onReset,
  onSave,
  onTest,
  purgePending,
}: {
  disabled: boolean;
  group: InstanceSettingGroup;
  onPurgeEmbeddingCache: () => void;
  onReset: () => void;
  onSave: () => void;
  onTest: () => void;
  purgePending: boolean;
}) => (
  <div className="flex flex-wrap items-center justify-between gap-2">
    <div className="flex flex-wrap gap-2">
      <Button disabled={disabled} onClick={onSave}>
        <Save className="size-3.5" />
        Save changes
      </Button>
      <Button disabled={disabled} onClick={onTest} variant="outline">
        <TestTube2 className="size-3.5" />
        Test
      </Button>
      <Button disabled={disabled} onClick={onReset} variant="outline">
        <RotateCcw className="size-3.5" />
        Reset
      </Button>
    </div>
    {group === "security" && (
      <Button disabled={purgePending} onClick={onPurgeEmbeddingCache} variant="destructive">
        <Trash2 className="size-3.5" />
        Purge embedding cache
      </Button>
    )}
  </div>
);
