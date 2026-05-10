import { RotateCcw, Save, ShieldCheck, TestTube2, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
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

type DraftValue = boolean | string;

const GROUP_COPY: Record<InstanceSettingGroup, { title: string; description: string }> = {
  security: {
    title: "Security",
    description: "Browser, cookie, proxy, and outbound network policies.",
  },
  ingestion: {
    title: "Ingestion",
    description: "Document upload, conversion, OCR, and worker controls.",
  },
  storage: {
    title: "Storage",
    description: "Document binary storage for local disk, S3, and MinIO deployments.",
  },
  vector_store: {
    title: "Vector store",
    description: "Vector backend selection, cloud credentials, and provider-specific indexes.",
  },
  queue: {
    title: "Queue",
    description: "Queue backpressure and ingestion job limits.",
  },
  search: {
    title: "Search",
    description: "Query caches, collection caches, and embedding concurrency.",
  },
  chat: {
    title: "Chat",
    description: "Default chat provider behavior and model context budgets.",
  },
  webhooks: {
    title: "Webhooks",
    description: "Webhook limits, delivery timeouts, and retry cadence.",
  },
  retention: {
    title: "Retention",
    description: "Operational log retention policies.",
  },
  backups: {
    title: "Backups",
    description: "S3-compatible destination for readable full-instance backup exports.",
  },
};

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
  const copy = GROUP_COPY[group];
  const restartCount = groupSpecs.filter((spec) => spec.restart_required).length;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-4" />
              {copy.title}
            </CardTitle>
            <CardDescription>{copy.description}</CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant={restartCount ? "warning" : "success"} dot>
              {restartCount ? `${restartCount} restart-bound` : "applies live"}
            </Badge>
            <Badge variant="neutral" dot>
              {groupSpecs.length} settings
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {isPending ? (
          <div className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground">
            Loading settings…
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
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

        <div className="flex flex-wrap gap-2">
          <Button disabled={isPending || save.isPending} onClick={() => save.mutate(body())}>
            <Save className="size-4" />
            Save
          </Button>
          <Button
            disabled={isPending || test.isPending}
            onClick={() => test.mutate(body())}
            variant="outline"
          >
            <TestTube2 className="size-4" />
            Test
          </Button>
          <Button
            disabled={isPending || reset.isPending}
            onClick={() => reset.mutate(groupSpecs.map((spec) => spec.key))}
            variant="outline"
          >
            <RotateCcw className="size-4" />
            Reset tab
          </Button>
          {group === "security" && (
            <Button
              disabled={purgeEmbeddingCache.isPending}
              onClick={() => {
                if (window.confirm("Purge every persistent embedding cache row?")) {
                  purgeEmbeddingCache.mutate();
                }
              }}
              variant="destructive"
            >
              <Trash2 className="size-4" />
              Purge embedding cache
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
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
      <div className="rounded-md border border-border px-3 py-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold">{spec.label}</div>
            <div className="mt-1 text-xs text-muted-foreground">{description}</div>
          </div>
          <Switch checked={Boolean(value)} onCheckedChange={onChange} aria-label={spec.label} />
        </div>
        <SettingBadges spec={spec} setting={setting} />
      </div>
    );
  }
  if (spec.kind === "select") {
    return (
      <div className="rounded-md border border-border px-3 py-3">
        <Select
          label={spec.label}
          value={String(value ?? "")}
          onChange={onChange}
          options={spec.options.map((option) => ({ label: option, value: option }))}
        />
        <div className="mt-1 text-xs text-muted-foreground">{description}</div>
        <SettingBadges spec={spec} setting={setting} />
      </div>
    );
  }
  if (spec.kind === "string_list" || spec.kind === "int_list") {
    return (
      <div className="rounded-md border border-border px-3 py-3">
        <Textarea
          label={spec.label}
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
          description={description}
        />
        <SettingBadges spec={spec} setting={setting} />
      </div>
    );
  }
  return (
    <div className="rounded-md border border-border px-3 py-3">
      <Input
        label={spec.label}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        placeholder={spec.secret && setting?.has_value ? "Saved" : undefined}
        type={inputType(spec)}
        description={description}
      />
      <SettingBadges spec={spec} setting={setting} />
    </div>
  );
};

const SettingBadges = ({
  spec,
  setting,
}: {
  spec: InstanceSettingSpec;
  setting?: InstanceSettingValue;
}) => (
  <div className="mt-3 flex flex-wrap gap-2">
    <Badge variant={setting?.source === "database" ? "primary" : "neutral"}>
      {setting?.source ?? "default"}
    </Badge>
    <Badge variant={spec.restart_required ? "warning" : "success"}>
      {spec.restart_required ? "restart" : "live"}
    </Badge>
    {spec.secret && <Badge variant="neutral">secret</Badge>}
  </div>
);

const settingDescription = (spec: InstanceSettingSpec, setting?: InstanceSettingValue) => {
  if (spec.secret && setting?.has_value) {
    return `${spec.description} Leave blank to keep the saved value.`;
  }
  return spec.description;
};

const inputType = (spec: InstanceSettingSpec) => {
  if (spec.kind === "int" || spec.kind === "float") return "number";
  if (spec.kind === "secret") return "password";
  return "text";
};

const draftValue = (spec: InstanceSettingSpec, setting?: InstanceSettingValue): DraftValue => {
  if (spec.kind === "bool") return Boolean(setting?.value ?? spec.default ?? false);
  if (spec.kind === "secret") return "";
  const value = setting?.value ?? spec.default;
  if (Array.isArray(value)) return value.join("\n");
  return value === null || value === undefined ? "" : String(value);
};

const valuesForSubmit = (
  specs: InstanceSettingSpec[],
  draft: Record<string, DraftValue>,
): Record<string, unknown> => {
  const values: Record<string, unknown> = {};
  for (const spec of specs) {
    const value = draft[spec.key];
    if (spec.kind === "secret" && !value) continue;
    values[spec.key] = value;
  }
  return values;
};
