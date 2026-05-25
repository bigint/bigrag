import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { runWithConcurrency } from "@/lib/concurrency";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { UploadSession, UploadSessionFileResponse } from "@/types/bigrag";

const uploadConcurrency = 4;
const uploadSessionPollMs = 2_000;
const terminalUploadSessionStatuses = new Set<UploadSession["status"]>([
  "complete",
  "failed",
  "canceled",
]);

const uploadSessionFileName = (file: File) =>
  (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;

const uploadSessionClientId = (file: File, index: number) =>
  `${index}:${uploadSessionFileName(file)}:${file.size}:${file.lastModified}`;

export const useUploadSession = (collection: string, sessionId: string | null) => {
  const queryKey = useMemo(
    () => queryKeys.documents.uploadSession({ collection, id: sessionId }),
    [collection, sessionId],
  );
  const enabled = Boolean(collection && sessionId);
  return useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      apiClient.get<UploadSession>(
        `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${sessionId}`,
        { signal },
      ),
    enabled,
    refetchInterval: (query) => {
      const session = query.state.data;
      return session && terminalUploadSessionStatuses.has(session.status)
        ? false
        : uploadSessionPollMs;
    },
  });
};

export const useUploadSessionDocuments = (
  collection: string,
  options?: { onSessionStart?: (session: UploadSession) => void },
) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (files: File[]) => {
      const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
      const session = await apiClient.post<UploadSession>(
        `v1/collections/${encodeURIComponent(collection)}/upload-sessions`,
        {
          total_files: files.length,
          total_bytes: totalBytes,
          metadata: {},
        },
      );
      options?.onSessionStart?.(session);
      const errors: { filename: string; error: string }[] = [];
      await runWithConcurrency(files, uploadConcurrency, async (file, index) => {
        const form = new FormData();
        form.append("client_item_id", uploadSessionClientId(file, index));
        form.append("file", file, uploadSessionFileName(file));
        try {
          await apiClient.postForm<UploadSessionFileResponse>(
            `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${session.id}/files`,
            form,
          );
        } catch (err) {
          errors.push({
            filename: uploadSessionFileName(file),
            error: err instanceof Error ? err.message : "Upload failed",
          });
        }
      });
      const sessionPath = `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${session.id}`;
      const finalSession =
        errors.length < files.length
          ? await apiClient.post<UploadSession>(`${sessionPath}/complete`)
          : await apiClient.get<UploadSession>(sessionPath);
      return { errors, session: finalSession };
    },
    onSuccess: ({ errors, session }) => {
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      qc.invalidateQueries({
        queryKey: queryKeys.documents.uploadSession({ collection, id: session.id }),
      });
      if (errors.length) {
        toast.warning(`${errors.length} file${errors.length === 1 ? "" : "s"} need retry`);
      } else {
        toast.success(
          `Queued ${session.uploaded_files} file${session.uploaded_files === 1 ? "" : "s"}`,
        );
      }
    },
    onError: errorToast("Upload session failed"),
  });
};

export const useCancelUploadSession = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiClient.post<{ status: string; message: string }>(
        `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${sessionId}/cancel`,
      ),
    onSuccess: (_res, sessionId) => {
      qc.invalidateQueries({
        queryKey: queryKeys.documents.uploadSession({ collection, id: sessionId }),
      });
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      toast.success("Upload session canceled");
    },
    onError: errorToast("Cancel failed"),
  });
};
