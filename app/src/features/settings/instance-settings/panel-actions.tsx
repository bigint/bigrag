import { Save, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  type SettingsGroupLayout,
  type SettingsStatusSummary,
  settingsRecommendedAction,
} from "@/features/settings/settings-layout";
import { cn } from "@/lib/cn";
import type { InstanceSettingGroup } from "@/types/bigrag";

export const PanelActions = ({
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
