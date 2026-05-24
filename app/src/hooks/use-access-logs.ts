import { useMemo } from "react";
import { useRealtimeSnapshotQuery } from "@/hooks/use-realtime-snapshot-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { AccessLogFilters, AccessLogListResponse, AccessLogOverview } from "@/types/bigrag";

export type { AccessLogFilters };

const compactFilters = (filters: AccessLogFilters & { include_total?: boolean }) =>
  Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ""),
  ) as Record<string, string | number | boolean>;

export const useAccessOverview = (enabled: boolean, windowDays = 7) => {
  const queryKey = useMemo(() => queryKeys.access.overview({ windowDays }), [windowDays]);
  return useRealtimeSnapshotQuery<AccessLogOverview>({
    queryKey,
    queryFn: () =>
      apiClient.get<AccessLogOverview>("v1/admin/access/overview", { window_days: windowDays }),
    enabled,
    topic: "admin.access.overview",
    params: { window_days: windowDays },
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
  return useRealtimeSnapshotQuery<AccessLogListResponse>({
    queryKey,
    queryFn: () => apiClient.get<AccessLogListResponse>("v1/admin/access/logs", searchParams),
    enabled,
    topic: "admin.access.logs",
    params: searchParams,
  });
};
