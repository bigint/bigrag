"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { S3Job } from "@/types/bigrag";

type S3JobListResponse = { jobs: S3Job[]; total: number };

export type CreateS3JobBody = {
  bucket: string;
  prefix?: string;
  region?: string;
  endpoint_url?: string;
  access_key?: string;
  secret_key?: string;
  no_sign_request?: boolean;
  file_types?: string[];
  metadata?: Record<string, unknown>;
};

export const s3JobsKey = (collection: string) => ["s3-jobs", collection] as const;

export const useS3Jobs = (collection: string) =>
  useQuery({
    queryKey: s3JobsKey(collection),
    queryFn: () =>
      apiClient.get<S3JobListResponse>(`v1/collections/${encodeURIComponent(collection)}/s3-jobs`, {
        limit: 100,
      }),
    enabled: !!collection,
    refetchInterval: (q) => {
      const jobs = (q.state.data as S3JobListResponse | undefined)?.jobs ?? [];
      const live = jobs.some(
        (j) => j.status === "pending" || j.status === "listing" || j.status === "ingesting",
      );
      return live ? 2_000 : 10_000;
    },
  });

export const useCreateS3Job = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateS3JobBody) =>
      apiClient.post<{ status: string; message: string }>(
        `v1/collections/${encodeURIComponent(collection)}/documents/s3`,
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: s3JobsKey(collection) });
      toast.success("S3 ingestion job started");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to start S3 job"),
  });
};

export const useDeleteS3Job = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      apiClient.delete<{ status: string }>(
        `v1/collections/${encodeURIComponent(collection)}/s3-jobs/${jobId}`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: s3JobsKey(collection) });
      toast.success("Job deleted");
    },
  });
};

export const useResyncS3Job = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      apiClient.post<{ status: string }>(
        `v1/collections/${encodeURIComponent(collection)}/s3-jobs/${jobId}/resync`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: s3JobsKey(collection) });
      toast.success("Resync queued");
    },
  });
};
