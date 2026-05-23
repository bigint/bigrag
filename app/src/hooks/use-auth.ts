import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HTTPError } from "ky";
import { toast } from "sonner";
import { closeAllRealtimeStreams } from "@/hooks/use-realtime-snapshot-query";
import { AUTH_TIMEOUT_MS, apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

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

type UpdateCurrentUserProfileBody = {
  id: string;
  display_name: string;
  email: string;
};

export const useSetupStatus = () =>
  useQuery({
    queryKey: queryKeys.auth.setupStatus(),
    queryFn: ({ signal }) =>
      apiClient.get<{ needs_setup: boolean }>("v1/auth/setup-status", {
        signal,
        timeoutMs: AUTH_TIMEOUT_MS,
      }),
    staleTime: (query) => (query.state.data?.needs_setup === false ? Infinity : 0),
    retry: false,
  });

export const useSession = () =>
  useQuery({
    queryKey: queryKeys.auth.session(),
    queryFn: async ({ signal }) => {
      try {
        return await apiClient.get<SessionResponse>("v1/auth/me", {
          signal,
          timeoutMs: AUTH_TIMEOUT_MS,
        });
      } catch (err) {
        if (err instanceof HTTPError && err.response.status === 401) {
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
      qc.setQueryData(queryKeys.auth.session(), data);
      qc.invalidateQueries({ queryKey: queryKeys.auth.all() });
    },
  });
};

export const useLogout = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<void>("v1/auth/logout"),
    onSuccess: () => {
      closeAllRealtimeStreams();
      qc.clear();
      qc.setQueryData(queryKeys.auth.session(), null);
      toast.success("Signed out");
    },
  });
};

export const useLogoutAll = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<void>("v1/auth/logout-all"),
    onSuccess: () => {
      closeAllRealtimeStreams();
      qc.clear();
      qc.setQueryData(queryKeys.auth.session(), null);
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
      qc.setQueryData(queryKeys.auth.session(), data);
      qc.invalidateQueries({ queryKey: queryKeys.auth.all() });
    },
  });
};

export const useUpdateCurrentUserProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: UpdateCurrentUserProfileBody) =>
      apiClient.patch<CurrentUser>(`v1/admin/users/${encodeURIComponent(id)}`, body),
    onSuccess: (user) => {
      qc.setQueryData<SessionResponse>(queryKeys.auth.session(), { user });
      qc.invalidateQueries({ queryKey: queryKeys.auth.all() });
      toast.success("Profile updated");
    },
  });
};

export const useChangePassword = () =>
  useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      apiClient.post<{ status: string; message: string }>("v1/auth/password", body),
  });
