import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { AccessLogFilters, AccessLogListResponse, AccessLogOverview } from "@/types/bigrag";

const statusPollMs = 5_000;

const compactFilters = (filters: AccessLogFilters & { include_total?: boolean }) =>
  Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ""),
  ) as Record<string, string | number | boolean>;

export const useAccessOverview = (enabled: boolean, windowDays = 7) => {
  const queryKey = useMemo(() => queryKeys.access.overview({ windowDays }), [windowDays]);
  return useQuery({
    queryKey,
    queryFn: () =>
      apiClient.get<AccessLogOverview>("v1/admin/status/access", { window_days: windowDays }),
    enabled,
    refetchInterval: enabled ? statusPollMs : false,
  });
};

export const useAccessLogs = (filters: AccessLogFilters, enabled = true) => {
  const {
    action,
    actor_id,
    collection,
    limit,
    method,
    offset,
    path: pathFilter,
    status_family,
    success,
  } = filters;
  const searchParams = useMemo(
    () =>
      compactFilters({
        action,
        actor_id,
        collection,
        include_total: true,
        limit,
        method,
        offset,
        path: pathFilter,
        status_family,
        success,
      }),
    [action, actor_id, collection, limit, method, offset, pathFilter, status_family, success],
  );
  const queryKey = useMemo(() => queryKeys.access.logs(searchParams), [searchParams]);
  return useQuery({
    queryKey,
    queryFn: () => apiClient.get<AccessLogListResponse>("v1/admin/access/logs", searchParams),
    enabled,
  });
};
