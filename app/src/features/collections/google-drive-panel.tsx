import { Search } from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  DriveBreadcrumb,
  DriveBrowser,
  DriveHeader,
  SelectedBar,
} from "@/features/collections/google-drive-browser";
import {
  DEFAULT_GOOGLE_DRIVE_BROWSER_STATE,
  GOOGLE_DRIVE_ROOT_FOLDER,
  useGoogleDriveBrowserStore,
} from "@/features/collections/google-drive-browser-store";
import {
  useSyncJobsBySource,
  useVisibleGoogleDriveFiles,
} from "@/features/collections/google-drive-panel-hooks";
import { activeGoogleSyncStatuses } from "@/features/collections/google-drive-progress";
import { SourcesPanel } from "@/features/collections/google-drive-sources-panel";
import { ConnectRequired, SetupRequired } from "@/features/collections/google-drive-states";
import { SyncMonitor } from "@/features/collections/google-drive-sync-monitor";
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
  const folderStack = useGoogleDriveBrowserStore(
    (state) =>
      state.browsers[collection]?.folderStack ?? DEFAULT_GOOGLE_DRIVE_BROWSER_STATE.folderStack,
  );
  const pageToken = useGoogleDriveBrowserStore((state) => state.browsers[collection]?.pageToken);
  const search = useGoogleDriveBrowserStore(
    (state) => state.browsers[collection]?.search ?? DEFAULT_GOOGLE_DRIVE_BROWSER_STATE.search,
  );
  const visibleFiles = useGoogleDriveBrowserStore(
    (state) =>
      state.browsers[collection]?.visibleFiles ?? DEFAULT_GOOGLE_DRIVE_BROWSER_STATE.visibleFiles,
  );
  const selected = useGoogleDriveBrowserStore(
    (state) => state.browsers[collection]?.selected ?? DEFAULT_GOOGLE_DRIVE_BROWSER_STATE.selected,
  );
  const clearSelected = useGoogleDriveBrowserStore((state) => state.clearSelected);
  const goBack = useGoogleDriveBrowserStore((state) => state.goBack);
  const openFolder = useGoogleDriveBrowserStore((state) => state.openFolder);
  const setPageToken = useGoogleDriveBrowserStore((state) => state.setPageToken);
  const setSearch = useGoogleDriveBrowserStore((state) => state.setSearch);
  const syncVisibleFiles = useGoogleDriveBrowserStore((state) => state.syncVisibleFiles);
  const toggleSelected = useGoogleDriveBrowserStore((state) => state.toggleSelected);

  const configured = account.data?.configured ?? false;
  const connected = account.data?.connected ?? false;
  const currentFolder = folderStack.at(-1) ?? GOOGLE_DRIVE_ROOT_FOLDER;
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

  useVisibleGoogleDriveFiles(collection, files.data, pageToken, syncVisibleFiles);

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
    clearSelected(collection);
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
              onBack={() => goBack(collection)}
            />
            <Input
              aria-label="Search Drive"
              onChange={(e) => {
                setSearch(collection, e.target.value);
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
            onOpenFolder={(item) => openFolder(collection, item)}
            onToggleSelected={(item, checked) => toggleSelected(collection, item, checked)}
            selected={selected}
          />

          {files.data?.next_page_token && (
            <div className="flex justify-center">
              <Button
                onClick={() => setPageToken(collection, files.data?.next_page_token ?? undefined)}
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
          onClear={() => clearSelected(collection)}
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
