import { beforeEach, describe, expect, it } from "vitest";
import {
  GOOGLE_DRIVE_ROOT_FOLDER,
  useGoogleDriveBrowserStore,
} from "@/features/collections/google-drive-browser-store";
import type { GoogleDriveFile, GoogleDriveFileList } from "@/types/bigrag";

const resetDriveStore = () => {
  useGoogleDriveBrowserStore.setState({ browsers: {} });
};

const file = (id: string, sourceType: "file" | "folder" = "file"): GoogleDriveFile => ({
  id,
  mime_type: sourceType === "folder" ? "application/vnd.google-apps.folder" : "text/plain",
  modified_time: null,
  name: id,
  size: sourceType === "folder" ? null : 12,
  source_type: sourceType,
  sync_supported: true,
  unsupported_reason: null,
  web_url: null,
});

const fileList = (
  files: GoogleDriveFile[],
  pageToken: string | null = null,
): GoogleDriveFileList => ({
  files,
  next_page_token: pageToken,
  parent_id: "root",
  provider: "google_drive",
  query: "",
});

describe("useGoogleDriveBrowserStore", () => {
  beforeEach(() => {
    resetDriveStore();
  });

  it("opens folders and goes back without leaving stale pagination or results", () => {
    const store = useGoogleDriveBrowserStore.getState();

    store.setSearch("docs", "policy");
    store.syncVisibleFiles("docs", fileList([file("a")]), undefined);
    store.setPageToken("docs", "next");
    store.openFolder("docs", file("folder-a", "folder"));

    expect(useGoogleDriveBrowserStore.getState().browsers.docs).toMatchObject({
      folderStack: [GOOGLE_DRIVE_ROOT_FOLDER, { id: "folder-a", name: "folder-a" }],
      pageToken: undefined,
      search: "",
      visibleFiles: [],
    });

    useGoogleDriveBrowserStore.getState().goBack("docs");

    expect(useGoogleDriveBrowserStore.getState().browsers.docs).toMatchObject({
      folderStack: [GOOGLE_DRIVE_ROOT_FOLDER],
      pageToken: undefined,
      visibleFiles: [],
    });
  });

  it("resets page state on search changes and appends paged results without duplicates", () => {
    const first = file("first");
    const second = file("second");
    const duplicate = file("first");

    useGoogleDriveBrowserStore.getState().setSearch("docs", "invoice");
    useGoogleDriveBrowserStore.getState().syncVisibleFiles("docs", fileList([first]), undefined);
    useGoogleDriveBrowserStore.getState().setPageToken("docs", "page-2");
    useGoogleDriveBrowserStore
      .getState()
      .syncVisibleFiles("docs", fileList([duplicate, second]), "page-2");

    expect(useGoogleDriveBrowserStore.getState().browsers.docs).toMatchObject({
      pageToken: "page-2",
      search: "invoice",
      visibleFiles: [first, second],
    });

    useGoogleDriveBrowserStore.getState().setSearch("docs", "updated");

    expect(useGoogleDriveBrowserStore.getState().browsers.docs).toMatchObject({
      pageToken: undefined,
      search: "updated",
      visibleFiles: [],
    });
  });

  it("tracks selected files per collection and clears the current selection", () => {
    const first = file("first");
    const second = file("second");

    useGoogleDriveBrowserStore.getState().toggleSelected("docs", first, true);
    useGoogleDriveBrowserStore.getState().toggleSelected("docs", second, true);
    useGoogleDriveBrowserStore.getState().toggleSelected("other", file("other"), true);
    useGoogleDriveBrowserStore.getState().toggleSelected("docs", first, false);

    expect(useGoogleDriveBrowserStore.getState().browsers.docs.selected).toEqual({
      second,
    });
    expect(useGoogleDriveBrowserStore.getState().browsers.other.selected).toEqual({
      other: file("other"),
    });

    useGoogleDriveBrowserStore.getState().clearSelected("docs");

    expect(useGoogleDriveBrowserStore.getState().browsers.docs.selected).toEqual({});
    expect(useGoogleDriveBrowserStore.getState().browsers.other.selected).toEqual({
      other: file("other"),
    });
  });
});
