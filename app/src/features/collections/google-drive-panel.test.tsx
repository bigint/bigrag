import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { GoogleDrivePanel } from "./google-drive-panel";

const noop = vi.hoisted(() => vi.fn());

type BrowserStoreMock = {
  browsers: Record<string, unknown>;
  clearSelected: typeof noop;
  goBack: typeof noop;
  openFolder: typeof noop;
  setPageToken: typeof noop;
  setSearch: typeof noop;
  syncVisibleFiles: typeof noop;
  toggleSelected: typeof noop;
};

vi.mock("@/features/collections/google-drive-browser-store", () => ({
  DEFAULT_GOOGLE_DRIVE_BROWSER_STATE: {
    folderStack: [{ id: "root", name: "My Drive" }],
    pageToken: undefined,
    search: "",
    selected: {},
    visibleFiles: [],
  },
  GOOGLE_DRIVE_ROOT_FOLDER: { id: "root", name: "My Drive" },
  useGoogleDriveBrowserStore: <T,>(selector: (state: BrowserStoreMock) => T) =>
    selector({
      browsers: {},
      clearSelected: noop,
      goBack: noop,
      openFolder: noop,
      setPageToken: noop,
      setSearch: noop,
      syncVisibleFiles: noop,
      toggleSelected: noop,
    }),
}));

vi.mock("@/features/collections/google-drive-panel-hooks", () => ({
  useSyncJobsBySource: () => new Map(),
  useVisibleGoogleDriveFiles: vi.fn(),
}));

vi.mock("@/hooks/use-google-drive", () => ({
  useCreateGoogleSource: () => ({ isPending: false, mutate: vi.fn() }),
  useDeleteGoogleSource: () => ({ isPending: false, mutate: vi.fn() }),
  useGoogleAccount: () => ({
    data: {
      configured: true,
      connected: true,
      email: "ops@example.com",
      status: "connected",
    },
  }),
  useGoogleDriveFiles: () => ({
    data: { files: [], next_page_token: null },
    error: null,
    isError: false,
    isFetching: false,
    isPending: false,
  }),
  useGoogleSources: () => ({
    data: {
      sources: [
        {
          account_email: "ops@example.com",
          collection_name: "docs",
          created_at: "2026-05-15T12:00:00Z",
          id: "source_1",
          last_error: null,
          last_sync_at: null,
          metadata: {},
          next_sync_at: null,
          provider: "google_drive",
          root_id: "folder_1",
          root_mime_type: "application/vnd.google-apps.folder",
          root_name: "Runbooks",
          schedule_enabled: true,
          source_type: "folder",
          status: "idle",
          sync_interval_hours: 24,
          updated_at: "2026-05-15T12:00:00Z",
        },
      ],
      total: 1,
    },
    isPending: false,
  }),
  useGoogleSyncJobs: () => ({ data: { jobs: [], total: 0 }, isPending: false, streaming: true }),
  useSyncGoogleSource: () => ({ isPending: false, mutate: vi.fn() }),
  useUpdateGoogleSource: () => ({ isPending: false, mutate: vi.fn() }),
}));

vi.mock("@/hooks/use-platform", () => ({
  usePlatformStats: () => ({
    data: {
      collections: 1,
      documents: {
        failed: 0,
        pending: 0,
        processing: 0,
        ready: 0,
        total: 0,
        total_chunks: 0,
        total_size_bytes: 0,
        total_tokens: 0,
      },
      queue: {
        completed: 0,
        failed: 0,
        pending: 0,
        processing: 0,
        queued: 0,
      },
      webhooks: 0,
      workers: {
        heartbeat_age_seconds: 240,
        heartbeat_at: "2026-05-15T12:00:00Z",
        online: false,
      },
    },
  }),
}));

describe("GoogleDrivePanel", () => {
  it("warns and disables manual sync while the worker is offline", () => {
    const html = renderToStaticMarkup(<GoogleDrivePanel collection="docs" />);

    expect(html).toContain("bigrag-worker is offline");
    expect(html).toContain("Scheduled syncs wait until bigrag-worker is online.");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*aria-label="Sync source"/);
  });
});
