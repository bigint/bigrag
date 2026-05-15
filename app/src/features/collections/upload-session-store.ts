import { create } from "zustand";
import { type PersistStorage, persist, type StorageValue } from "zustand/middleware";

export type UploadSessionStoreState = {
  activeSessionIds: Record<string, string>;
  clearActiveSessionId: (collection: string) => void;
  setActiveSessionId: (collection: string, sessionId: string) => void;
};

type PersistedUploadSessionState = Pick<UploadSessionStoreState, "activeSessionIds">;

const STORAGE_KEY = "bigrag:upload-sessions";

const getLocalStorage = () => {
  if (typeof globalThis.localStorage === "undefined") return null;
  return globalThis.localStorage;
};

const uploadSessionStorage: PersistStorage<PersistedUploadSessionState> = {
  getItem: (name) => {
    const value = getLocalStorage()?.getItem(name);
    return value ? (JSON.parse(value) as StorageValue<PersistedUploadSessionState>) : null;
  },
  removeItem: (name) => {
    getLocalStorage()?.removeItem(name);
  },
  setItem: (name, value) => {
    getLocalStorage()?.setItem(name, JSON.stringify(value));
  },
};

export const useUploadSessionStore = create<UploadSessionStoreState>()(
  persist(
    (set) => ({
      activeSessionIds: {},
      clearActiveSessionId: (collection) =>
        set((state) => {
          const activeSessionIds = { ...state.activeSessionIds };
          delete activeSessionIds[collection];
          return { activeSessionIds };
        }),
      setActiveSessionId: (collection, sessionId) =>
        set((state) => ({
          activeSessionIds: {
            ...state.activeSessionIds,
            [collection]: sessionId,
          },
        })),
    }),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({ activeSessionIds: state.activeSessionIds }),
      storage: uploadSessionStorage,
      version: 1,
    },
  ),
);
