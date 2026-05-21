import { CheckCircle2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import type { EmbeddingPreset } from "@/types/bigrag";

type StepPanelProps = {
  readonly active: boolean;
  readonly children: ReactNode;
  readonly complete: boolean;
  readonly icon: LucideIcon;
  readonly index: number;
  readonly optional?: boolean;
  readonly title: string;
};

export const StepPanel = ({
  active,
  children,
  complete,
  icon: Icon,
  index,
  optional = false,
  title,
}: StepPanelProps) => (
  <section
    className={cn(
      "overflow-hidden rounded-md border bg-card transition-colors",
      active ? "border-foreground" : "border-border",
    )}
  >
    <header className="flex flex-wrap items-start justify-between gap-4 border-border border-b bg-muted/30 p-4">
      <div className="flex min-w-0 items-start gap-3">
        <div
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-md border",
            complete
              ? "border-success/30 bg-success/10 text-success"
              : active
                ? "border-primary/30 bg-primary/10 text-primary"
                : "border-border bg-background text-muted-foreground",
          )}
        >
          {complete ? <CheckCircle2 className="size-4" /> : <Icon className="size-4" />}
        </div>
        <div className="min-w-0">
          <div className="text-muted-foreground text-xs font-semibold">Step {index}</div>
          <h2 className="mt-0.5 font-semibold text-base tracking-normal">{title}</h2>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {optional && <Badge variant="neutral">optional</Badge>}
        <Badge dot variant={complete ? "success" : active ? "primary" : "neutral"}>
          {complete ? "complete" : active ? "active" : "pending"}
        </Badge>
      </div>
    </header>
    <div className="p-4">{children}</div>
  </section>
);

export const PresetSummary = ({
  preset,
  total,
}: {
  readonly preset: EmbeddingPreset;
  readonly total: number;
}) => (
  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div className="min-w-0">
      <div className="font-semibold text-sm">{preset.name}</div>
      <div className="mt-1 flex flex-wrap gap-2 text-muted-foreground text-xs">
        <span>{preset.provider}</span>
        <span>{preset.model}</span>
        <span>{preset.dimension}d</span>
      </div>
    </div>
    <div className="flex flex-wrap gap-2">
      <Badge dot variant={preset.has_api_key ? "success" : "warning"}>
        {preset.has_api_key ? "key set" : "key missing"}
      </Badge>
      {total > 1 && <Badge variant="neutral">{total} presets</Badge>}
    </div>
  </div>
);
