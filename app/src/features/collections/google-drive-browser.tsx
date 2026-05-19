import { Button, Checkbox, cn, Empty, Spinner, Tooltip } from "@atelier/ui";
import {
  ChevronLeft,
  Cloud,
  ExternalLink,
  File,
  Folder,
  FolderOpen,
  ListChecks,
  Search,
  TriangleAlert,
} from "lucide-react";
import { formatBytes, formatRelative } from "@/lib/format";
import type { GoogleDriveFile } from "@/types/bigrag";

export const DriveHeader = ({
  email,
  isAdding,
  offlineReason,
  onAddSelected,
  selectedCount,
  workerOffline,
}: {
  email: string | null | undefined;
  isAdding: boolean;
  offlineReason?: string;
  onAddSelected: () => void;
  selectedCount: number;
  workerOffline?: boolean;
}) => (
  <div className="flex flex-wrap items-center justify-between gap-3 border-border border-b bg-muted/35 px-4 py-4">
    <div className="flex min-w-0 items-center gap-3">
      <div className="flex size-10 shrink-0 items-center justify-center rounded-sm border border-border bg-background">
        <Cloud className="size-5" />
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{email ?? "Google Drive"}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">Drive source browser</div>
      </div>
    </div>
    <Button
      disabled={selectedCount === 0 || isAdding || workerOffline}
      onClick={onAddSelected}
      title={workerOffline ? offlineReason : undefined}
    >
      {isAdding ? <Spinner /> : <Cloud className="size-4" />}
      Add selected
    </Button>
  </div>
);

export const DriveBreadcrumb = ({
  canGoBack,
  currentFolder,
  onBack,
}: {
  canGoBack: boolean;
  currentFolder: string;
  onBack: () => void;
}) => (
  <div className="flex min-w-0 items-center gap-2 rounded-sm border border-border bg-background px-2 py-2">
    <Tooltip content="Back">
      <Button aria-label="Back" disabled={!canGoBack} onClick={onBack} size="icon" variant="ghost">
        <ChevronLeft className="size-4" />
      </Button>
    </Tooltip>
    <div className="min-w-0 flex-1">
      <div className="text-[11px] font-semibold uppercase text-muted-foreground">Location</div>
      <div className="truncate text-sm font-medium">{currentFolder}</div>
    </div>
  </div>
);

export const DriveBrowser = ({
  error,
  files,
  isError,
  isPending,
  onOpenFolder,
  onToggleSelected,
  selected,
}: {
  error: string;
  files: GoogleDriveFile[];
  isError: boolean;
  isPending: boolean;
  onOpenFolder: (item: GoogleDriveFile) => void;
  onToggleSelected: (item: GoogleDriveFile, checked: boolean) => void;
  selected: Record<string, GoogleDriveFile>;
}) => (
  <div className="min-h-[430px] overflow-hidden rounded-sm border border-border bg-background">
    {isPending ? (
      <div className="flex h-72 items-center justify-center">
        <Spinner />
      </div>
    ) : isError ? (
      <Empty
        bordered={false}
        className="py-16"
        description={error}
        icon={<TriangleAlert className="size-5" />}
        title="Drive files unavailable"
      />
    ) : files.length ? (
      <ul className="max-h-[560px] divide-y divide-border overflow-y-auto">
        {files.map((item) => (
          <DriveFileRow
            checked={Boolean(selected[item.id])}
            item={item}
            key={item.id}
            onOpenFolder={onOpenFolder}
            onToggleSelected={onToggleSelected}
          />
        ))}
      </ul>
    ) : (
      <Empty
        bordered={false}
        className="py-16"
        description="Try a different folder or search."
        icon={<Search className="size-5" />}
        title="No Drive files found"
      />
    )}
  </div>
);

const DriveFileRow = ({
  checked,
  item,
  onOpenFolder,
  onToggleSelected,
}: {
  checked: boolean;
  item: GoogleDriveFile;
  onOpenFolder: (item: GoogleDriveFile) => void;
  onToggleSelected: (item: GoogleDriveFile, checked: boolean) => void;
}) => {
  const canSelect = item.sync_supported;
  return (
    <li
      className={cn(
        "grid grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3",
        !canSelect && "bg-muted/45",
      )}
    >
      <Checkbox
        aria-label={`Select ${item.name}`}
        checked={checked}
        disabled={!canSelect}
        onCheckedChange={(isChecked) => onToggleSelected(item, isChecked)}
      />
      <div className="flex size-9 items-center justify-center rounded-sm border border-border bg-card text-muted-foreground">
        {item.source_type === "folder" ? (
          <Folder className="size-4" />
        ) : (
          <File className="size-4" />
        )}
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{item.name}</div>
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{item.source_type}</span>
          {item.size !== null && <span>{formatBytes(item.size)}</span>}
          {item.modified_time && <span>{formatRelative(item.modified_time)}</span>}
          {item.unsupported_reason && (
            <span className="text-warning">{item.unsupported_reason}</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1">
        {item.web_url && (
          <Tooltip content="Open in Google Drive">
            <Button
              aria-label="Open in Google Drive"
              onClick={() => window.open(item.web_url ?? undefined, "_blank")}
              size="icon"
              variant="ghost"
            >
              <ExternalLink className="size-4" />
            </Button>
          </Tooltip>
        )}
        {item.source_type === "folder" && (
          <Tooltip content="Open folder">
            <Button
              aria-label="Open folder"
              onClick={() => onOpenFolder(item)}
              size="icon"
              variant="outline"
            >
              <FolderOpen className="size-4" />
            </Button>
          </Tooltip>
        )}
      </div>
    </li>
  );
};

export const SelectedBar = ({
  isAdding,
  offlineReason,
  onAddSelected,
  onClear,
  selectedBytes,
  selectedCount,
  workerOffline,
}: {
  isAdding: boolean;
  offlineReason?: string;
  onAddSelected: () => void;
  onClear: () => void;
  selectedBytes: number;
  selectedCount: number;
  workerOffline?: boolean;
}) => (
  <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 border-border border-t bg-card/95 px-4 py-3">
    <div className="flex min-w-0 items-center gap-3">
      <div className="flex size-8 items-center justify-center rounded-sm bg-primary text-primary-foreground">
        <ListChecks className="size-4" />
      </div>
      <div className="min-w-0 text-sm">
        <span className="font-semibold">{selectedCount.toLocaleString()} selected</span>
        {selectedBytes > 0 && (
          <span className="text-muted-foreground"> - {formatBytes(selectedBytes)}</span>
        )}
      </div>
    </div>
    <div className="flex items-center gap-2">
      <Button disabled={selectedCount === 0 || isAdding} onClick={onClear} variant="outline">
        Clear
      </Button>
      <Button
        disabled={selectedCount === 0 || isAdding || workerOffline}
        onClick={onAddSelected}
        title={workerOffline ? offlineReason : undefined}
      >
        {isAdding ? <Spinner /> : <Cloud className="size-4" />}
        Sync selected
      </Button>
    </div>
  </div>
);
