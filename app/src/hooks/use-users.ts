"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { User } from "@/types/bigrag";

const KEY = ["users"] as const;

export const useUsers = () =>
  useQuery({
    queryKey: KEY,
    queryFn: () => apiClient.get<{ users: User[]; total: number }>("v1/admin/users"),
  });

export const useCreateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string; display_name?: string; role?: string }) =>
      apiClient.post<User>("v1/admin/users", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("User created");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create user"),
  });
};

export const useUpdateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: string;
      display_name?: string;
      role?: string;
      password?: string;
    }) => apiClient.patch<User>(`v1/admin/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
};

export const useDeleteUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<{ status: string }>(`v1/admin/users/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("User removed");
    },
  });
};
