"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";

export type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
};

type SessionResponse = { user: CurrentUser };

export const useSetupStatus = () =>
  useQuery({
    queryKey: ["auth", "setup-status"],
    queryFn: () => apiClient.get<{ needs_setup: boolean }>("v1/auth/setup-status"),
    staleTime: 0,
    retry: false,
  });

export const useSession = () =>
  useQuery({
    queryKey: ["auth", "session"],
    queryFn: async () => {
      try {
        return await apiClient.get<SessionResponse>("v1/auth/me");
      } catch (err: unknown) {
        if (err instanceof Error && "response" in err) {
          return null;
        }
        throw err;
      }
    },
    retry: false,
    staleTime: 30_000,
  });

export const useLogin = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      apiClient.post<SessionResponse>("v1/auth/login", body),
    onSuccess: (data) => {
      qc.setQueryData(["auth", "session"], data);
      qc.invalidateQueries({ queryKey: ["auth"] });
    },
  });
};

export const useLogout = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<void>("v1/auth/logout"),
    onSuccess: () => {
      qc.setQueryData(["auth", "session"], null);
      qc.invalidateQueries();
      toast.success("Signed out");
    },
  });
};

export const useLogoutAll = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<void>("v1/auth/logout-all"),
    onSuccess: () => {
      qc.setQueryData(["auth", "session"], null);
      qc.invalidateQueries();
      toast.success("Signed out of all devices");
    },
  });
};

export const useSetup = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string; display_name: string }) =>
      apiClient.post<SessionResponse>("v1/auth/setup", body),
    onSuccess: (data) => {
      qc.setQueryData(["auth", "session"], data);
      qc.invalidateQueries({ queryKey: ["auth"] });
    },
  });
};

export const useChangePassword = () =>
  useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      apiClient.post<{ status: string; message: string }>("v1/auth/password", body),
  });
