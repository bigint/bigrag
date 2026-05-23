import { type QueryClient, useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { toast } from "sonner";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { S3Source, S3SourceList, S3SyncJob, S3SyncJobList } from "@/types/bigrag";

export type CreateS3SourceBody = {
  collection_name: string;
  bucket: string;
  prefix?: string;
  region?: string;
  endpoint_url?: string | null;
  force_path_style?: boolean;
  access_key_id: string;
  secret_access_key: string;
  session_token?: string | null;
  schedule_enabled?: boolean;
  sync_interval_hours?: number;
  metadata?: Record<string, unknown>;
};

export type UpdateS3SourceBody = {
  bucket?: string | null;
  prefix?: string | null;
  region?: string | null;
  endpoint_url?: string | null;
  force_path_style?: boolean | null;
  access_key_id?: string | null;
  secret_access_key?: string | null;
  session_token?: string | null;
  schedule_enabled?: boolean | null;
  sync_interval_hours?: number | null;
  metadata?: Record<string, unknown> | null;
};

const updateS3SourcesCache = (
  queryClient: QueryClient,
  collection: string | undefined,
  update: (data: S3SourceList | undefined) => S3SourceList | undefined,
) => {
  for (const key of [
    queryKeys.connectors.s3Sources({ collection }),
    queryKeys.connectors.s3Sources(),
  ]) {
    queryClient.setQueryData<S3SourceList>(key, update);
  }
};

const invalidateS3SyncJobs = (queryClient: QueryClient) => {
  queryClient.invalidateQueries({
    queryKey: queryKeys.connectors.s3SyncJobsAll(),
  });
};

export const useS3Sources = (collection?: string) => {
  const queryKey = useMemo(() => queryKeys.connectors.s3Sources({ collection }), [collection]);
  const path = useMemo(() => {
    const params = new URLSearchParams();
    if (collection) params.set("collection", collection);
    const query = params.toString();
    return query ? `v1/admin/realtime/s3/sources?${query}` : "v1/admin/realtime/s3/sources";
  }, [collection]);
  return useSseSnapshotQuery<S3SourceList>({
    queryKey,
    queryFn: () =>
      apiClient.get<S3SourceList>("v1/connectors/s3/sources", {
        ...(collection ? { collection } : {}),
      }),
    path,
  });
};

export const useS3SyncJobs = ({
  collection,
  limit = 20,
  sourceId,
}: {
  collection?: string;
  limit?: number;
  sourceId?: string;
} = {}) => {
  const queryKey = useMemo(
    () => queryKeys.connectors.s3SyncJobs({ collection, limit, sourceId }),
    [collection, limit, sourceId],
  );
  const path = useMemo(() => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (collection) params.set("collection", collection);
    if (sourceId) params.set("source_id", sourceId);
    return `v1/admin/realtime/s3/sync-jobs?${params}`;
  }, [collection, limit, sourceId]);
  return useSseSnapshotQuery<S3SyncJobList>({
    queryKey,
    queryFn: () =>
      apiClient.get<S3SyncJobList>("v1/connectors/s3/sync-jobs", {
        limit,
        ...(collection ? { collection } : {}),
        ...(sourceId ? { source_id: sourceId } : {}),
      }),
    path,
  });
};

export const useCreateS3Source = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Omit<CreateS3SourceBody, "collection_name">) =>
      apiClient.post<S3Source>("v1/connectors/s3/sources", {
        collection_name: collection,
        ...body,
      }),
    onSuccess: (source) => {
      updateS3SourcesCache(qc, collection, (data) => {
        if (!data) return data;
        const sources = data.sources.filter((item) => item.id !== source.id);
        return { sources: [source, ...sources], total: sources.length + 1 };
      });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.s3Sources({ collection }) });
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      invalidateS3SyncJobs(qc);
      toast.success("S3 source syncing");
    },
    onError: errorToast("Could not add S3 source"),
  });
};

export const useSyncS3Source = (collection?: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) =>
      apiClient.post<S3SyncJob>(`v1/connectors/s3/sources/${sourceId}/sync`),
    onSuccess: (_job, sourceId) => {
      updateS3SourcesCache(qc, collection, (data) => {
        if (!data) return data;
        return {
          ...data,
          sources: data.sources.map((source) =>
            source.id === sourceId ? { ...source, status: "syncing" } : source,
          ),
        };
      });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.s3Sources({ collection }) });
      invalidateS3SyncJobs(qc);
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      toast.success("S3 sync queued");
    },
    onError: errorToast("Could not sync S3 source"),
  });
};

export const useUpdateS3Source = (collection?: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, body }: { sourceId: string; body: UpdateS3SourceBody }) =>
      apiClient.patch<S3Source>(`v1/connectors/s3/sources/${sourceId}`, body),
    onSuccess: (source) => {
      updateS3SourcesCache(qc, collection, (data) => {
        if (!data) return data;
        return {
          ...data,
          sources: data.sources.map((item) => (item.id === source.id ? source : item)),
        };
      });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.s3Sources({ collection }) });
      toast.success("S3 source updated");
    },
    onError: errorToast("Could not update S3 source"),
  });
};

export const useDeleteS3Source = (collection?: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) =>
      apiClient.delete<{ status: string }>(`v1/connectors/s3/sources/${sourceId}`),
    onSuccess: (_res, sourceId) => {
      updateS3SourcesCache(qc, collection, (data) => {
        if (!data) return data;
        const sources = data.sources.filter((source) => source.id !== sourceId);
        return { sources, total: sources.length };
      });
      qc.invalidateQueries({ queryKey: queryKeys.connectors.s3Sources({ collection }) });
      invalidateS3SyncJobs(qc);
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      toast.success("S3 source removed");
    },
    onError: errorToast("Could not remove S3 source"),
  });
};
