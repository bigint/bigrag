import { create } from "zustand";
import { type PersistStorage, persist, type StorageValue } from "zustand/middleware";

export type UploadSessionStoreState = {
  activeSessionIds: Record<string, string>;
  clearActiveSessionId: (collection: string) => void;
  migrateLegacyUploadSession: (collection: string) => void;
  setActiveSessionId: (collection: string, sessionId: string) => void;
};

type PersistedUploadSessionState = Pick<UploadSessionStoreState, "activeSessionIds">;

const STORAGE_KEY = "rag-computer:upload-sessions";

const legacyStorageKey = (collection: string) => `rag-computer:upload-session:${collection}`;

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
    (set, get) => ({
      activeSessionIds: {},
      clearActiveSessionId: (collection) =>
        set((state) => {
          const activeSessionIds = { ...state.activeSessionIds };
          delete activeSessionIds[collection];
          return { activeSessionIds };
        }),
      migrateLegacyUploadSession: (collection) => {
        const storage = getLocalStorage();
        const legacySessionId = storage?.getItem(legacyStorageKey(collection));
        if (!legacySessionId) return;
        if (!get().activeSessionIds[collection]) {
          set((state) => ({
            activeSessionIds: {
              ...state.activeSessionIds,
              [collection]: legacySessionId,
            },
          }));
        }
        storage?.removeItem(legacyStorageKey(collection));
      },
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
