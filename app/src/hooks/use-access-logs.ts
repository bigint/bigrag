"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { AccessLogListResponse, AccessLogOverview } from "@/types/bigrag";

export type AccessLogFilters = {
  action?: string;
  collection?: string;
  method?: string;
  path?: string;
  status_family?: "2xx" | "3xx" | "4xx" | "5xx";
  success?: boolean;
  limit?: number;
  offset?: number;
};

const compactFilters = (filters: AccessLogFilters) =>
  Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ""),
  ) as Record<string, string | number | boolean>;

export const useAccessOverview = (enabled: boolean, windowDays = 7) =>
  useQuery({
    queryKey: queryKeys.access.overview(windowDays),
    queryFn: () =>
      apiClient.get<AccessLogOverview>("v1/admin/access/overview", { window_days: windowDays }),
    enabled,
    refetchInterval: 20_000,
  });

export const useAccessLogs = (filters: AccessLogFilters, enabled = true) => {
  const searchParams = compactFilters(filters);
  return useQuery({
    queryKey: queryKeys.access.logs(searchParams),
    queryFn: () => apiClient.get<AccessLogListResponse>("v1/admin/access/logs", searchParams),
    enabled,
    refetchInterval: 20_000,
  });
};
