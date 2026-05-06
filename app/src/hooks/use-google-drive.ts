"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
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

export const useGoogleSources = (collection?: string) =>
  useQuery({
    queryKey: queryKeys.connectors.googleSources(collection),
    queryFn: () =>
      apiClient.get<GoogleSourceListResponse>("v1/connectors/google/sources", {
        ...(collection ? { collection } : {}),
      }),
    refetchInterval: (q) => {
      const data = q.state.data as GoogleSourceListResponse | undefined;
      return data?.sources.some((source) => source.status === "syncing") ? 2_500 : 10_000;
    },
  });

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
    onSuccess: () => {
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
    onSuccess: () => {
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
    onSuccess: () => {
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
