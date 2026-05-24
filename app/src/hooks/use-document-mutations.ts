import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";

export const useDeleteDocument = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) =>
      apiClient.delete<{ status: string }>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      toast.success("Document deleted");
    },
  });
};

export const useBatchDeleteDocuments = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (documentIds: string[]) =>
      apiClient.post<{
        status: string;
        deleted: number;
        errors: { document_id: string; error: string }[];
      }>(`v1/collections/${encodeURIComponent(collection)}/documents/batch/delete`, {
        document_ids: documentIds,
      }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      const failed = res.errors.length;
      if (failed) {
        toast.warning(`${res.deleted} deleted, ${failed} failed`);
      } else {
        toast.success(`${res.deleted} document${res.deleted === 1 ? "" : "s"} deleted`);
      }
    },
    onError: errorToast("Bulk delete failed"),
  });
};
