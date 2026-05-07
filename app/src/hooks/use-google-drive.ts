import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { toast } from "sonner";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type {
  GoogleAccount,
  GoogleConnectorConfig,
  GoogleDriveFileList,
  GoogleDriveSource,
  GoogleDriveSyncJob,
} from "@/types/bigrag";

type GoogleSourceListResponse = { sources: GoogleDriveSource[]; total: number };
type GoogleSyncJobListResponse = { jobs: GoogleDriveSyncJob[]; total: number };

const updateGoogleSourcesCache = (
  queryClient: QueryClient,
  collection: string,
  update: (data: GoogleSourceListResponse | undefined) => GoogleSourceListResponse | undefined,
) => {
  for (const key of [
    queryKeys.connectors.googleSources(collection),
    queryKeys.connectors.googleSources(),
  ]) {
    queryClient.setQueryData<GoogleSourceListResponse>(key, update);
  }
};

export const useGoogleConnectorConfig = () =>
  useQuery({
    queryKey: queryKeys.connectors.googleConfig(),
    queryFn: () => apiClient.get<GoogleConnectorConfig>("v1/admin/connectors/google"),
    retry: false,
  });

export const useUpdateGoogleConnectorConfig = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { enabled: boolean; client_id: string; client_secret?: string | null }) =>
      apiClient.put<GoogleConnectorConfig>("v1/admin/connectors/google", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.connectors.googleConfig() });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.googleAccount() });
      toast.success("Google Drive connector saved");
    },
    onError: errorToast("Could not save Google Drive connector"),
  });
};

export const useGoogleAccount = () =>
  useQuery({
    queryKey: queryKeys.connectors.googleAccount(),
    queryFn: () => apiClient.get<GoogleAccount>("v1/connectors/google/account"),
    retry: false,
  });

export const useGoogleDriveFiles = ({
  enabled,
  pageToken,
  parentId,
  query,
}: {
  enabled: boolean;
  pageToken?: string;
  parentId: string;
  query?: string;
}) =>
  useQuery({
    queryKey: queryKeys.connectors.googleFiles(parentId, query ?? "", pageToken ?? ""),
    queryFn: () =>
      apiClient.get<GoogleDriveFileList>("v1/connectors/google/files", {
        parent_id: parentId,
        ...(query ? { query } : {}),
        ...(pageToken ? { page_token: pageToken } : {}),
      }),
    enabled,
    retry: false,
  });

export const useGoogleSources = (collection?: string) => {
  const queryKey = useMemo(() => queryKeys.connectors.googleSources(collection), [collection]);
  const path = useMemo(() => {
    const params = new URLSearchParams();
    if (collection) params.set("collection", collection);
    return `v1/admin/realtime/google/sources?${params}`;
  }, [collection]);
  return useSseSnapshotQuery<GoogleSourceListResponse>({
    queryKey,
    queryFn: () =>
      apiClient.get<GoogleSourceListResponse>("v1/connectors/google/sources", {
        ...(collection ? { collection } : {}),
      }),
    path,
  });
};

export const useGoogleSyncJobs = (sourceId?: string, limit = 20) => {
  const queryKey = useMemo(() => queryKeys.connectors.googleSyncJobs(sourceId), [sourceId]);
  const path = useMemo(() => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (sourceId) params.set("source_id", sourceId);
    return `v1/admin/realtime/google/sync-jobs?${params}`;
  }, [limit, sourceId]);
  return useSseSnapshotQuery<GoogleSyncJobListResponse>({
    queryKey,
    queryFn: () =>
      apiClient.get<GoogleSyncJobListResponse>("v1/connectors/google/sync-jobs", {
        limit,
        ...(sourceId ? { source_id: sourceId } : {}),
      }),
    path,
  });
};

export const useCreateGoogleSource = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      root_id: string;
      root_name: string;
      root_mime_type: string;
      source_type?: "file" | "folder";
      metadata?: Record<string, unknown>;
    }) =>
      apiClient.post<GoogleDriveSource>("v1/connectors/google/sources", {
        collection_name: collection,
        ...body,
      }),
    onSuccess: (source) => {
      updateGoogleSourcesCache(qc, collection, (data) => {
        if (!data) return data;
        const sources = data.sources.filter((item) => item.id !== source.id);
        return { sources: [source, ...sources], total: sources.length + 1 };
      });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.googleSources(collection) });
      qc.invalidateQueries({ queryKey: queryKeys.documents.list(collection) });
      toast.success("Google Drive source syncing");
    },
    onError: errorToast("Could not add Google Drive source"),
  });
};

export const useSyncGoogleSource = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) =>
      apiClient.post<GoogleDriveSyncJob>(`v1/connectors/google/sources/${sourceId}/sync`),
    onSuccess: (_job, sourceId) => {
      updateGoogleSourcesCache(qc, collection, (data) => {
        if (!data) return data;
        return {
          ...data,
          sources: data.sources.map((source) =>
            source.id === sourceId ? { ...source, status: "syncing" } : source,
          ),
        };
      });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.googleSources(collection) });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.googleSyncJobs(sourceId) });
      qc.invalidateQueries({ queryKey: queryKeys.documents.list(collection) });
      toast.success("Google Drive sync queued");
    },
    onError: errorToast("Could not sync Google Drive source"),
  });
};

export const useUpdateGoogleSource = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      sourceId,
      body,
    }: {
      sourceId: string;
      body: { schedule_enabled?: boolean; sync_interval_hours?: number };
    }) => apiClient.patch<GoogleDriveSource>(`v1/connectors/google/sources/${sourceId}`, body),
    onSuccess: (source) => {
      updateGoogleSourcesCache(qc, collection, (data) => {
        if (!data) return data;
        return {
          ...data,
          sources: data.sources.map((item) => (item.id === source.id ? source : item)),
        };
      });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.googleSources(collection) });
      toast.success("Google Drive source updated");
    },
    onError: errorToast("Could not update Google Drive source"),
  });
};

export const useDeleteGoogleSource = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) =>
      apiClient.delete<{ status: string }>(`v1/connectors/google/sources/${sourceId}`),
    onSuccess: (_res, sourceId) => {
      updateGoogleSourcesCache(qc, collection, (data) => {
        if (!data) return data;
        const sources = data.sources.filter((source) => source.id !== sourceId);
        return { sources, total: sources.length };
      });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.googleSources(collection) });
      toast.success("Google Drive source removed");
    },
    onError: errorToast("Could not remove Google Drive source"),
  });
};

export const useDisconnectGoogle = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<{ status: string }>("v1/connectors/google/disconnect"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.connectors.googleAccount() });
      qc.invalidateQueries({ queryKey: ["connectors", "google", "files"] });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.googleSources() });
      toast.success("Google Drive disconnected");
    },
    onError: errorToast("Could not disconnect Google Drive"),
  });
};
