import { Button, Input, Spinner } from "@atelier/ui";
import { Search } from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";
import { useShallow } from "zustand/react/shallow";
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
  getWorkerAvailability,
  workerOfflineActionMessage,
} from "@/features/workers/worker-status";
import { WorkerOfflineBanner } from "@/features/workers/worker-status-banner";
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
import { usePlatformStats } from "@/hooks/use-platform";
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
  const { data: stats } = usePlatformStats();
  const createSource = useCreateGoogleSource(collection);
  const syncSource = useSyncGoogleSource(collection);
  const updateSource = useUpdateGoogleSource(collection);
  const deleteSource = useDeleteGoogleSource(collection);
  const {
    clearSelected,
    folderStack,
    goBack,
    openFolder,
    pageToken,
    search,
    selected,
    setPageToken,
    setSearch,
    syncVisibleFiles,
    toggleSelected,
    visibleFiles,
  } = useGoogleDriveBrowserStore(
    useShallow((state) => {
      const browser = state.browsers[collection];
      return {
        clearSelected: state.clearSelected,
        folderStack: browser?.folderStack ?? DEFAULT_GOOGLE_DRIVE_BROWSER_STATE.folderStack,
        goBack: state.goBack,
        openFolder: state.openFolder,
        pageToken: browser?.pageToken,
        search: browser?.search ?? DEFAULT_GOOGLE_DRIVE_BROWSER_STATE.search,
        selected: browser?.selected ?? DEFAULT_GOOGLE_DRIVE_BROWSER_STATE.selected,
        setPageToken: state.setPageToken,
        setSearch: state.setSearch,
        syncVisibleFiles: state.syncVisibleFiles,
        toggleSelected: state.toggleSelected,
        visibleFiles: browser?.visibleFiles ?? DEFAULT_GOOGLE_DRIVE_BROWSER_STATE.visibleFiles,
      };
    }),
  );

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
  const workerAvailability = getWorkerAvailability(stats);
  const workerOffline = workerAvailability.offline;
  const offlineReason = workerOffline ? workerOfflineActionMessage(workerAvailability) : undefined;

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
    if (workerOffline) {
      toast.warning(workerOfflineActionMessage(workerAvailability));
      return;
    }
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
    <div className="flex flex-col gap-4">
      <WorkerOfflineBanner availability={workerAvailability} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="min-w-0 overflow-hidden rounded-sm border border-border bg-card">
          <DriveHeader
            email={account.data?.email}
            isAdding={createSource.isPending}
            offlineReason={offlineReason}
            onAddSelected={addSelected}
            selectedCount={selectedItems.length}
            workerOffline={workerOffline}
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
            offlineReason={offlineReason}
            onAddSelected={addSelected}
            onClear={() => clearSelected(collection)}
            selectedBytes={selectedBytes}
            selectedCount={selectedItems.length}
            workerOffline={workerOffline}
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
            offlineReason={offlineReason}
            sources={sources.data?.sources ?? []}
            sourcesPending={sources.isPending}
            syncSource={syncSource}
            updateSource={updateSource}
            workerOffline={workerOffline}
          />
        </aside>
      </div>
    </div>
  );
};
