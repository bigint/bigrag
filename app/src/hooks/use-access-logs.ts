import { useMemo } from "react";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { AccessLogListResponse, AccessLogOverview } from "@/types/bigrag";

type AccessLogFilters = {
  action?: string;
  actor_id?: string;
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

export const useAccessOverview = (enabled: boolean, windowDays = 7) => {
  const queryKey = useMemo(() => queryKeys.access.overview({ windowDays }), [windowDays]);
  return useSseSnapshotQuery<AccessLogOverview>({
    queryKey,
    queryFn: () =>
      apiClient.get<AccessLogOverview>("v1/admin/access/overview", { window_days: windowDays }),
    enabled,
    path: `v1/admin/realtime/access/overview?window_days=${windowDays}`,
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
  const ssePath = useMemo(() => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(searchParams)) {
      params.set(key, String(value));
    }
    return `v1/admin/realtime/access/logs?${params}`;
  }, [searchParams]);
  return useSseSnapshotQuery<AccessLogListResponse>({
    queryKey,
    queryFn: () => apiClient.get<AccessLogListResponse>("v1/admin/access/logs", searchParams),
    enabled,
    path: ssePath,
  });
};
