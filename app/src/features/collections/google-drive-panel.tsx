import {
  ChevronLeft,
  Cloud,
  ExternalLink,
  FileText,
  Folder,
  FolderSync,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import {
  useCreateGoogleSource,
  useDeleteGoogleSource,
  useGoogleAccount,
  useGoogleDriveFiles,
  useGoogleSources,
  useSyncGoogleSource,
  useUpdateGoogleSource,
} from "@/hooks/use-google-drive";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatBytes, formatRelative } from "@/lib/format";
import type { GoogleDriveFile, GoogleDriveSource } from "@/types/bigrag";

const ROOT_FOLDER = { id: "root", name: "My Drive" };

const statusVariant: Record<GoogleDriveSource["status"], "success" | "warning" | "info" | "error"> =
  {
    idle: "success",
    syncing: "info",
    needs_reauth: "warning",
    error: "error",
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
  const fileError =
    files.error instanceof Error
      ? files.error.message
      : "Could not load Google Drive files. Try again.";

  useEffect(() => {
    if (!files.data) return;
    setVisibleFiles((current) => {
      if (!pageToken) return files.data.files;
      const seen = new Set(current.map((item) => item.id));
      return [...current, ...files.data.files.filter((item) => !seen.has(item.id))];
    });
  }, [files.data, pageToken]);

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

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="flex min-h-[520px] flex-col gap-4">
        {!configured ? (
          <SetupRequired />
        ) : !connected ? (
          <ConnectRequired
            needsReauth={account.data?.status === "needs_reauth"}
            onConnect={() => void connect()}
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border px-4 py-3">
              <div>
                <div className="text-sm font-medium">{account.data?.email ?? "Google Drive"}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  Select files or folders to sync into this collection.
                </div>
              </div>
              <Button
                disabled={selectedItems.length === 0 || createSource.isPending}
                onClick={addSelected}
              >
                {createSource.isPending ? <Spinner /> : <Cloud className="size-4" />}
                Add selected
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                aria-label="Back"
                disabled={folderStack.length === 1 || !!query}
                onClick={goBack}
                size="icon"
                variant="outline"
              >
                <ChevronLeft className="size-4" />
              </Button>
              <div className="min-w-0 flex-1 text-sm font-medium">
                <span className="text-muted-foreground">Location / </span>
                <span className="truncate">{query ? "Search results" : currentFolder.name}</span>
              </div>
            </div>

            <Input
              label="Search Drive"
              onChange={(e) => {
                setSearch(e.target.value);
                setPageToken(undefined);
                setVisibleFiles([]);
              }}
              placeholder="Search files and folders"
              trailing={files.isFetching ? <Spinner /> : <Search className="size-4" />}
              value={search}
            />

            <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-border">
              {files.isPending ? (
                <div className="flex h-64 items-center justify-center">
                  <Spinner />
                </div>
              ) : files.isError ? (
                <div className="px-4 py-8 text-center text-sm text-destructive">{fileError}</div>
              ) : visibleFiles.length ? (
                <ul className="max-h-[390px] divide-y divide-border overflow-y-auto">
                  {visibleFiles.map((item) => {
                    const checked = Boolean(selected[item.id]);
                    const canSelect = item.sync_supported;
                    return (
                      <li
                        className={cn(
                          "flex items-center gap-3 px-4 py-3",
                          !canSelect && "bg-muted/35",
                        )}
                        key={item.id}
                      >
                        <Checkbox
                          aria-label={`Select ${item.name}`}
                          checked={checked}
                          disabled={!canSelect}
                          onCheckedChange={(isChecked) => toggleSelected(item, isChecked)}
                        />
                        {item.source_type === "folder" ? (
                          <Folder className="size-4 shrink-0 text-muted-foreground" />
                        ) : (
                          <FileText className="size-4 shrink-0 text-muted-foreground" />
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium">{item.name}</div>
                          <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            <span>{item.source_type}</span>
                            {item.size !== null && <span>{formatBytes(item.size)}</span>}
                            {item.modified_time && (
                              <span>modified {formatRelative(item.modified_time)}</span>
                            )}
                            {item.unsupported_reason && (
                              <span className="text-warning">{item.unsupported_reason}</span>
                            )}
                          </div>
                        </div>
                        {item.web_url && (
                          <Button
                            aria-label="Open in Google Drive"
                            onClick={() => window.open(item.web_url ?? undefined, "_blank")}
                            size="icon"
                            variant="ghost"
                          >
                            <ExternalLink className="size-4" />
                          </Button>
                        )}
                        {item.source_type === "folder" && (
                          <Button onClick={() => openFolder(item)} size="sm" variant="outline">
                            Open
                          </Button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                  No Drive files found.
                </div>
              )}
            </div>

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
          </>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Sources</h3>
          {sources.isPending && <Spinner />}
        </div>
        {sources.data?.sources.length ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <ul className="max-h-[580px] divide-y divide-border overflow-y-auto">
              {sources.data.sources.map((source) => (
                <li className="flex flex-col gap-3 px-4 py-3" key={source.id}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex min-w-0 items-center gap-2">
                        <FolderSync className="size-4 shrink-0 text-muted-foreground" />
                        <span className="truncate text-sm font-medium">{source.root_name}</span>
                        <Badge dot variant={statusVariant[source.status]}>
                          {source.status}
                        </Badge>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                        <span>{source.source_type}</span>
                        {source.last_sync_at && (
                          <span>last {formatRelative(source.last_sync_at)}</span>
                        )}
                        {source.next_sync_at && (
                          <span>next {formatRelative(source.next_sync_at)}</span>
                        )}
                      </div>
                      {source.last_error && (
                        <div className="mt-1 text-xs text-destructive">{source.last_error}</div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        aria-label="Sync source"
                        disabled={syncSource.isPending || source.status === "syncing"}
                        onClick={() => syncSource.mutate(source.id)}
                        size="icon"
                        variant="outline"
                      >
                        <RefreshCw className="size-4" />
                      </Button>
                      <Button
                        aria-label="Remove source"
                        disabled={deleteSource.isPending}
                        onClick={() => deleteSource.mutate(source.id)}
                        size="icon"
                        variant="ghost"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <Switch
                      checked={source.schedule_enabled}
                      disabled={updateSource.isPending}
                      label="Scheduled"
                      onCheckedChange={(checked) =>
                        updateSource.mutate({
                          sourceId: source.id,
                          body: { schedule_enabled: checked },
                        })
                      }
                    />
                    <Select
                      className="w-36"
                      disabled={updateSource.isPending || !source.schedule_enabled}
                      onChange={(value) =>
                        updateSource.mutate({
                          sourceId: source.id,
                          body: { sync_interval_hours: Number(value) },
                        })
                      }
                      options={intervalOptions}
                      value={String(source.sync_interval_hours)}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            No Drive sources connected.
          </div>
        )}
      </div>
    </div>
  );
};

const SetupRequired = () => (
  <div className="flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3">
    <div>
      <div className="text-sm font-medium">Connector setup required</div>
      <div className="mt-0.5 text-xs text-muted-foreground">
        Add Google OAuth credentials in settings.
      </div>
    </div>
    <Button
      onClick={() => {
        window.location.href = "/settings?tab=connectors";
      }}
      variant="outline"
    >
      <ExternalLink className="size-4" />
      Settings
    </Button>
  </div>
);

const ConnectRequired = ({
  needsReauth,
  onConnect,
}: {
  needsReauth: boolean;
  onConnect: () => void;
}) => (
  <div className="flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3">
    <div>
      <div className="text-sm font-medium">
        {needsReauth ? "Reconnect Google Drive" : "Connect Google Drive"}
      </div>
      <div className="mt-0.5 text-xs text-muted-foreground">
        Authorize Drive read access, then choose files inside bigRAG.
      </div>
    </div>
    <Button onClick={onConnect}>{needsReauth ? "Reconnect" : "Connect Google"}</Button>
  </div>
);
