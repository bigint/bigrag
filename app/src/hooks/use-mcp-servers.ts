import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { CreatedMcpServer, McpServer } from "@/types/bigrag";

const KEY = queryKeys.mcpServers();

export const useMcpServers = () =>
  useQuery({
    queryKey: KEY,
    queryFn: () => apiClient.get<{ servers: McpServer[]; total: number }>("v1/admin/mcp-servers"),
  });

export const useCreateMcpServer = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; server_name: string; collection?: string | null }) =>
      apiClient.post<CreatedMcpServer>("v1/admin/mcp-servers", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
    onError: errorToast("Failed to create"),
  });
};

export const useRotateMcpServer = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.post<CreatedMcpServer>(`v1/admin/mcp-servers/${id}/rotate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
    onError: errorToast("Failed to rotate"),
  });
};

export const useDeleteMcpServer = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<{ status: string }>(`v1/admin/mcp-servers/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("MCP server deleted");
    },
  });
};
