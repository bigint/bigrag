import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  type SettingsGroupLayout,
  type SettingsStatusSummary,
  settingsRecommendedAction,
} from "@/features/settings/settings-layout";

export const PanelHeader = ({
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

export const CollapsedPanel = ({
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
