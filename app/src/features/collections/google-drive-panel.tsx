import {
  ChevronLeft,
  Cloud,
  ExternalLink,
  File,
  Folder,
  FolderOpen,
  FolderSync,
  HardDriveDownload,
  ListChecks,
  RefreshCw,
  Search,
  Settings,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useEffect,
  useMemo,
  useState,
} from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import {
  activeGoogleSyncStatuses,
  clampGoogleSyncProgress,
  googleSyncCountLabel,
  googleSyncProgressForJob,
  googleSyncProgressLabel,
  isActiveGoogleSyncJob,
} from "@/features/collections/google-drive-progress";
import {
  useCreateGoogleSource,
  useDeleteGoogleSource,
  useGoogleAccount,
  useGoogleDriveFiles,
  useGoogleSources,
  useGoogleSyncJobs,
  useSyncGoogleSource,
  useUpdateGoogleSource,
} from "@/hooks/use-google-drive";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatBytes, formatRelative } from "@/lib/format";
import type {
  GoogleDriveFile,
  GoogleDriveFileList,
  GoogleDriveSource,
  GoogleDriveSyncJob,
  GoogleSyncProgress,
} from "@/types/rag-computer";

const ROOT_FOLDER = { id: "root", name: "My Drive" };

const statusVariant: Record<GoogleDriveSource["status"], "success" | "warning" | "info" | "error"> =
  {
    error: "error",
    idle: "success",
    needs_reauth: "warning",
    syncing: "info",
  };

const jobVariant: Record<GoogleDriveSyncJob["status"], "success" | "warning" | "info" | "error"> = {
  complete: "success",
  failed: "error",
  pending: "warning",
  running: "info",
};

const intervalOptions = [
  { label: "Hourly", value: "1" },
  { label: "Daily", value: "24" },
  { label: "Weekly", value: "168" },
] as const;

export const GoogleDrivePanel = ({
  active = true,
  collection,
}: {
  active?: boolean;
  collection: string;
}) => {
  const account = useGoogleAccount();
  const sources = useGoogleSources(collection);
  const syncJobs = useGoogleSyncJobs({ collection, limit: 20 });
  const createSource = useCreateGoogleSource(collection);
  const syncSource = useSyncGoogleSource(collection);
  const updateSource = useUpdateGoogleSource(collection);
  const deleteSource = useDeleteGoogleSource(collection);
  const [folderStack, setFolderStack] = useState([ROOT_FOLDER]);
  const [pageToken, setPageToken] = useState<string | undefined>();
  const [search, setSearch] = useState("");
  const [visibleFiles, setVisibleFiles] = useState<GoogleDriveFile[]>([]);
  const [selected, setSelected] = useState<Record<string, GoogleDriveFile>>({});

  const configured = account.data?.configured ?? false;
  const connected = account.data?.connected ?? false;
  const currentFolder = folderStack.at(-1) ?? ROOT_FOLDER;
  const query = search.trim();
  const files = useGoogleDriveFiles({
    enabled: active && connected,
    pageToken,
    parentId: currentFolder.id,
    query: query || undefined,
  });
  const selectedItems = useMemo(() => Object.values(selected), [selected]);
  const selectedBytes = selectedItems.reduce((sum, item) => sum + (item.size ?? 0), 0);
  const syncJobsBySource = useSyncJobsBySource(syncJobs.data?.jobs);
  const activeJob = useMemo(
    () =>
      syncJobs.data?.jobs.find((job) => activeGoogleSyncStatuses.has(job.status)) ??
      syncJobs.data?.jobs[0],
    [syncJobs.data?.jobs],
  );
  const fileError =
    files.error instanceof Error
      ? files.error.message
      : "Could not load Google Drive files. Try again.";

  useVisibleGoogleDriveFiles(files.data, pageToken, setVisibleFiles);

  const connect = async () => {
    const redirect = `${window.location.pathname}${window.location.search}`;
    try {
      const { auth_url } = await apiClient.get<{ auth_url: string }>(
        "v1/connectors/google/oauth/start-url",
        { redirect_path: redirect },
      );
      window.location.href = auth_url;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start Google OAuth");
    }
  };

  const addSelected = () => {
    for (const item of selectedItems) {
      createSource.mutate({
        root_id: item.id,
        root_name: item.name,
        root_mime_type: item.mime_type,
        source_type: item.source_type,
      });
    }
    setSelected({});
  };

  const openFolder = (item: GoogleDriveFile) => {
    if (item.source_type !== "folder") return;
    setFolderStack((stack) => [...stack, { id: item.id, name: item.name }]);
    setPageToken(undefined);
    setSearch("");
    setVisibleFiles([]);
  };

  const goBack = () => {
    setFolderStack((stack) => (stack.length > 1 ? stack.slice(0, -1) : stack));
    setPageToken(undefined);
    setVisibleFiles([]);
  };

  const toggleSelected = (item: GoogleDriveFile, checked: boolean) => {
    setSelected((current) => {
      const next = { ...current };
      if (checked) {
        next[item.id] = item;
      } else {
        delete next[item.id];
      }
      return next;
    });
  };

  if (!configured) return <SetupRequired />;
  if (!connected) {
    return (
      <ConnectRequired
        email={account.data?.email}
        needsReauth={account.data?.status === "needs_reauth"}
        onConnect={() => void connect()}
      />
    );
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <section className="min-w-0 overflow-hidden rounded-sm border border-border bg-card">
        <DriveHeader
          email={account.data?.email}
          isAdding={createSource.isPending}
          onAddSelected={addSelected}
          selectedCount={selectedItems.length}
        />
        <div className="flex flex-col gap-4 p-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
            <DriveBreadcrumb
              canGoBack={folderStack.length > 1 && !query}
              currentFolder={query ? "Search results" : currentFolder.name}
              onBack={goBack}
            />
            <Input
              aria-label="Search Drive"
              onChange={(e) => {
                setSearch(e.target.value);
                setPageToken(undefined);
                setVisibleFiles([]);
              }}
              placeholder="Search Drive"
              trailing={files.isFetching ? <Spinner /> : <Search className="size-4" />}
              value={search}
            />
          </div>

          <DriveBrowser
            error={fileError}
            files={visibleFiles}
            isError={files.isError}
            isPending={files.isPending}
            onOpenFolder={openFolder}
            onToggleSelected={toggleSelected}
            selected={selected}
          />

          {files.data?.next_page_token && (
            <div className="flex justify-center">
              <Button
                onClick={() => setPageToken(files.data?.next_page_token ?? undefined)}
                variant="outline"
              >
                Load more
              </Button>
            </div>
          )}
        </div>
        <SelectedBar
          isAdding={createSource.isPending}
          onAddSelected={addSelected}
          onClear={() => setSelected({})}
          selectedBytes={selectedBytes}
          selectedCount={selectedItems.length}
        />
      </section>

      <aside className="flex min-w-0 flex-col gap-4">
        <SyncMonitor
          isPending={syncJobs.isPending}
          job={activeJob}
          streaming={syncJobs.streaming}
        />
        <SourcesPanel
          deleteSource={deleteSource}
          jobsBySource={syncJobsBySource}
          sources={sources.data?.sources ?? []}
          sourcesPending={sources.isPending}
          syncSource={syncSource}
          updateSource={updateSource}
        />
      </aside>
    </div>
  );
};

const DriveHeader = ({
  email,
  isAdding,
  onAddSelected,
  selectedCount,
}: {
  email: string | null | undefined;
  isAdding: boolean;
  onAddSelected: () => void;
  selectedCount: number;
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
    <Button disabled={selectedCount === 0 || isAdding} onClick={onAddSelected}>
      {isAdding ? <Spinner /> : <Cloud className="size-4" />}
      Add selected
    </Button>
  </div>
);

const DriveBreadcrumb = ({
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

const DriveBrowser = ({
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

const SelectedBar = ({
  isAdding,
  onAddSelected,
  onClear,
  selectedBytes,
  selectedCount,
}: {
  isAdding: boolean;
  onAddSelected: () => void;
  onClear: () => void;
  selectedBytes: number;
  selectedCount: number;
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
      <Button disabled={selectedCount === 0 || isAdding} onClick={onAddSelected}>
        {isAdding ? <Spinner /> : <Cloud className="size-4" />}
        Sync selected
      </Button>
    </div>
  </div>
);

const SyncMonitor = ({
  isPending,
  job,
  streaming,
}: {
  isPending: boolean;
  job: GoogleDriveSyncJob | undefined;
  streaming: boolean;
}) => {
  if (isPending) {
    return (
      <section className="rounded-sm border border-border bg-card p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Sync monitor</h3>
          <Spinner />
        </div>
      </section>
    );
  }
  if (!job) {
    return (
      <section className="rounded-sm border border-border bg-card p-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-border">
            <HardDriveDownload className="size-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">Sync monitor</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">No sync jobs yet</p>
          </div>
        </div>
      </section>
    );
  }

  const progress = googleSyncProgressForJob(job);
  return (
    <section className="rounded-sm border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Sync monitor</h3>
            {streaming && <span className="size-1.5 rounded-full bg-success" />}
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {googleSyncProgressLabel(progress)}
          </p>
        </div>
        <Badge dot variant={jobVariant[job.status]}>
          {job.status}
        </Badge>
      </div>
      <div className="mt-4">
        <ProgressBar progress={progress} />
      </div>
      <SyncCounters progress={progress} />
      {job.error_message && (
        <div className="mt-3 text-xs text-destructive">{job.error_message}</div>
      )}
    </section>
  );
};

const SourcesPanel = ({
  deleteSource,
  jobsBySource,
  sources,
  sourcesPending,
  syncSource,
  updateSource,
}: {
  deleteSource: ReturnType<typeof useDeleteGoogleSource>;
  jobsBySource: Map<string, GoogleDriveSyncJob>;
  sources: GoogleDriveSource[];
  sourcesPending: boolean;
  syncSource: ReturnType<typeof useSyncGoogleSource>;
  updateSource: ReturnType<typeof useUpdateGoogleSource>;
}) => (
  <section className="min-w-0 overflow-hidden rounded-sm border border-border bg-card">
    <div className="flex items-center justify-between border-border border-b px-4 py-3">
      <h3 className="text-sm font-semibold">Sources</h3>
      {sourcesPending && <Spinner />}
    </div>
    {sources.length ? (
      <ul className="max-h-[640px] divide-y divide-border overflow-y-auto">
        {sources.map((source) => (
          <SourceRow
            deleteSource={deleteSource}
            job={jobsBySource.get(source.id)}
            key={source.id}
            source={source}
            syncSource={syncSource}
            updateSource={updateSource}
          />
        ))}
      </ul>
    ) : (
      <Empty
        bordered={false}
        className="py-12"
        description="Selected Drive files and folders appear here."
        icon={<FolderSync className="size-5" />}
        title="No Drive sources"
      />
    )}
  </section>
);

const SourceRow = ({
  deleteSource,
  job,
  source,
  syncSource,
  updateSource,
}: {
  deleteSource: ReturnType<typeof useDeleteGoogleSource>;
  job: GoogleDriveSyncJob | undefined;
  source: GoogleDriveSource;
  syncSource: ReturnType<typeof useSyncGoogleSource>;
  updateSource: ReturnType<typeof useUpdateGoogleSource>;
}) => {
  const progress = job ? googleSyncProgressForJob(job) : undefined;
  const isSyncing = source.status === "syncing" || isActiveGoogleSyncJob(job);
  return (
    <li className="flex flex-col gap-3 px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <FolderSync className="size-4 shrink-0 text-muted-foreground" />
            <span className="truncate text-sm font-semibold">{source.root_name}</span>
            <Badge dot variant={statusVariant[source.status]}>
              {source.status}
            </Badge>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>{source.source_type}</span>
            {source.last_sync_at && <span>last {formatRelative(source.last_sync_at)}</span>}
            {source.next_sync_at && <span>next {formatRelative(source.next_sync_at)}</span>}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Tooltip content="Sync now">
            <Button
              aria-label="Sync source"
              disabled={syncSource.isPending || isSyncing}
              onClick={() => syncSource.mutate(source.id)}
              size="icon"
              variant="outline"
            >
              <RefreshCw className="size-4" />
            </Button>
          </Tooltip>
          <Tooltip content="Remove source">
            <Button
              aria-label="Remove source"
              disabled={deleteSource.isPending}
              onClick={() => deleteSource.mutate(source.id)}
              size="icon"
              variant="ghost"
            >
              <Trash2 className="size-4" />
            </Button>
          </Tooltip>
        </div>
      </div>
      {progress && (
        <div className="rounded-sm border border-border bg-background p-3">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="min-w-0 truncate text-muted-foreground">
              {googleSyncProgressLabel(progress)}
            </span>
            <span className="font-semibold">
              {clampGoogleSyncProgress(progress.progress_percent)}%
            </span>
          </div>
          <div className="mt-2">
            <ProgressBar compact progress={progress} />
          </div>
        </div>
      )}
      {source.last_error && <div className="text-xs text-destructive">{source.last_error}</div>}
      <div className="flex flex-wrap items-center gap-3">
        <Switch
          checked={source.schedule_enabled}
          disabled={updateSource.isPending}
          label="Scheduled"
          onCheckedChange={(checked) =>
            updateSource.mutate({
              body: { schedule_enabled: checked },
              sourceId: source.id,
            })
          }
        />
        <Select
          className="w-36"
          disabled={updateSource.isPending || !source.schedule_enabled}
          onChange={(value) =>
            updateSource.mutate({
              body: { sync_interval_hours: Number(value) },
              sourceId: source.id,
            })
          }
          options={intervalOptions}
          value={String(source.sync_interval_hours)}
        />
      </div>
    </li>
  );
};

const ProgressBar = ({
  compact = false,
  progress,
}: {
  compact?: boolean;
  progress: GoogleSyncProgress;
}) => {
  const value = clampGoogleSyncProgress(progress.progress_percent);
  return (
    <div>
      <div
        aria-label="Sync progress"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={value}
        className={cn("h-2 overflow-hidden rounded-full bg-muted", compact && "h-1.5")}
        role="progressbar"
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${value}%` }} />
      </div>
      {!compact && (
        <div className="mt-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>{googleSyncCountLabel(progress)}</span>
          <span className="font-semibold text-foreground">{value}%</span>
        </div>
      )}
    </div>
  );
};

const SyncCounters = ({ progress }: { progress: GoogleSyncProgress }) => {
  const counts = [
    ["Created", progress.counts.created],
    ["Updated", progress.counts.updated],
    ["Skipped", progress.counts.skipped],
    ["Deleted", progress.counts.deleted],
    ["Failed", progress.counts.failed],
  ] as const;
  return (
    <div className="mt-4 grid grid-cols-5 gap-2">
      {counts.map(([label, value]) => (
        <div
          className="rounded-sm border border-border bg-background px-2 py-2 text-center"
          key={label}
        >
          <div className="text-sm font-semibold">{value.toLocaleString()}</div>
          <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{label}</div>
        </div>
      ))}
    </div>
  );
};

const SetupRequired = () => (
  <ConnectorState
    action={
      <Button
        onClick={() => {
          window.location.href = "/settings?tab=connectors";
        }}
      >
        <Settings className="size-4" />
        Settings
      </Button>
    }
    icon={<Settings className="size-5" />}
    label="Connector setup required"
    value="Add Google OAuth credentials in settings."
  />
);

const ConnectRequired = ({
  email,
  needsReauth,
  onConnect,
}: {
  email: string | null | undefined;
  needsReauth: boolean;
  onConnect: () => void;
}) => (
  <ConnectorState
    action={<Button onClick={onConnect}>{needsReauth ? "Reconnect" : "Connect Google"}</Button>}
    icon={needsReauth ? <TriangleAlert className="size-5" /> : <Cloud className="size-5" />}
    label={needsReauth ? "Reconnect Google Drive" : "Connect Google Drive"}
    value={email ?? "Authorize Drive read access."}
  />
);

const ConnectorState = ({
  action,
  icon,
  label,
  value,
}: {
  action: ReactNode;
  icon: ReactNode;
  label: string;
  value: string;
}) => (
  <div className="rounded-sm border border-border bg-card p-5">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-11 shrink-0 items-center justify-center rounded-sm border border-border bg-background">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold">{label}</div>
          <div className="mt-0.5 truncate text-xs text-muted-foreground">{value}</div>
        </div>
      </div>
      {action}
    </div>
  </div>
);

const useSyncJobsBySource = (jobs: GoogleDriveSyncJob[] | undefined) =>
  useMemo(() => {
    const map = new Map<string, GoogleDriveSyncJob>();
    for (const job of jobs ?? []) {
      if (!job.source_id) continue;
      if (!map.has(job.source_id)) map.set(job.source_id, job);
    }
    return map;
  }, [jobs]);

const useVisibleGoogleDriveFiles = (
  fileList: GoogleDriveFileList | undefined,
  pageToken: string | undefined,
  setVisibleFiles: Dispatch<SetStateAction<GoogleDriveFile[]>>,
) => {
  useEffect(() => {
    if (!fileList) return;
    setVisibleFiles((current) => {
      if (!pageToken) return fileList.files;
      const seen = new Set(current.map((item) => item.id));
      return [...current, ...fileList.files.filter((item) => !seen.has(item.id))];
    });
  }, [fileList, pageToken, setVisibleFiles]);
};
