import { create } from "zustand";
import type { GoogleDriveFile, GoogleDriveFileList } from "@/types/rag-computer";

export type GoogleDriveFolder = {
  id: string;
  name: string;
};

export type GoogleDriveBrowserState = {
  folderStack: GoogleDriveFolder[];
  pageToken: string | undefined;
  search: string;
  selected: Record<string, GoogleDriveFile>;
  visibleFiles: GoogleDriveFile[];
};

export type GoogleDriveBrowserStoreState = {
  browsers: Record<string, GoogleDriveBrowserState>;
  clearSelected: (collection: string) => void;
  goBack: (collection: string) => void;
  openFolder: (collection: string, item: GoogleDriveFile) => void;
  setPageToken: (collection: string, pageToken: string | undefined) => void;
  setSearch: (collection: string, search: string) => void;
  syncVisibleFiles: (
    collection: string,
    fileList: GoogleDriveFileList | undefined,
    pageToken: string | undefined,
  ) => void;
  toggleSelected: (collection: string, item: GoogleDriveFile, checked: boolean) => void;
};

export const GOOGLE_DRIVE_ROOT_FOLDER = { id: "root", name: "My Drive" } as const;

export const DEFAULT_GOOGLE_DRIVE_BROWSER_STATE = {
  folderStack: [GOOGLE_DRIVE_ROOT_FOLDER],
  pageToken: undefined,
  search: "",
  selected: {},
  visibleFiles: [],
} satisfies GoogleDriveBrowserState;

const createBrowserState = (): GoogleDriveBrowserState => ({
  folderStack: [GOOGLE_DRIVE_ROOT_FOLDER],
  pageToken: undefined,
  search: "",
  selected: {},
  visibleFiles: [],
});

const updateBrowser = (
  browsers: Record<string, GoogleDriveBrowserState>,
  collection: string,
  update: (browser: GoogleDriveBrowserState) => GoogleDriveBrowserState,
) => ({
  browsers: {
    ...browsers,
    [collection]: update(browsers[collection] ?? createBrowserState()),
  },
});

export const useGoogleDriveBrowserStore = create<GoogleDriveBrowserStoreState>((set) => ({
  browsers: {},
  clearSelected: (collection) =>
    set((state) =>
      updateBrowser(state.browsers, collection, (browser) => ({
        ...browser,
        selected: {},
      })),
    ),
  goBack: (collection) =>
    set((state) =>
      updateBrowser(state.browsers, collection, (browser) => ({
        ...browser,
        folderStack:
          browser.folderStack.length > 1 ? browser.folderStack.slice(0, -1) : browser.folderStack,
        pageToken: undefined,
        visibleFiles: [],
      })),
    ),
  openFolder: (collection, item) =>
    set((state) => {
      if (item.source_type !== "folder") return state;
      return updateBrowser(state.browsers, collection, (browser) => ({
        ...browser,
        folderStack: [...browser.folderStack, { id: item.id, name: item.name }],
        pageToken: undefined,
        search: "",
        visibleFiles: [],
      }));
    }),
  setPageToken: (collection, pageToken) =>
    set((state) =>
      updateBrowser(state.browsers, collection, (browser) => ({
        ...browser,
        pageToken,
      })),
    ),
  setSearch: (collection, search) =>
    set((state) =>
      updateBrowser(state.browsers, collection, (browser) => ({
        ...browser,
        pageToken: undefined,
        search,
        visibleFiles: [],
      })),
    ),
  syncVisibleFiles: (collection, fileList, pageToken) =>
    set((state) => {
      if (!fileList) return state;
      return updateBrowser(state.browsers, collection, (browser) => {
        if (!pageToken) {
          return { ...browser, visibleFiles: fileList.files };
        }
        const seen = new Set(browser.visibleFiles.map((item) => item.id));
        return {
          ...browser,
          visibleFiles: [
            ...browser.visibleFiles,
            ...fileList.files.filter((item) => !seen.has(item.id)),
          ],
        };
      });
    }),
  toggleSelected: (collection, item, checked) =>
    set((state) =>
      updateBrowser(state.browsers, collection, (browser) => {
        const selected = { ...browser.selected };
        if (checked) {
          selected[item.id] = item;
        } else {
          delete selected[item.id];
        }
        return { ...browser, selected };
      }),
    ),
}));
