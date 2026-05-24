import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { queryKeys } from "@/lib/query-keys";
import type { Collection, PlatformStats } from "@/types/bigrag";
import type { Paginated } from "@/types/pagination";

export const useOverviewAutoRefresh = (
  stats: PlatformStats | undefined,
  collectionsData: Paginated<"collections", Collection> | undefined,
) => {
  const queryClient = useQueryClient();
  const markerRef = useRef<string | null>(null);
  const docs = stats?.documents;
  const marker = [
    stats?.collections ?? "",
    docs?.total ?? "",
    docs?.ready ?? "",
    docs?.pending ?? "",
    docs?.processing ?? "",
    docs?.failed ?? "",
  ].join(":");

  useEffect(() => {
    if (!stats || !collectionsData) return;
    if (markerRef.current === null) {
      markerRef.current = marker;
      return;
    }
    if (markerRef.current === marker) return;
    markerRef.current = marker;
    void queryClient.invalidateQueries({ queryKey: queryKeys.collections.all() });
  }, [marker, collectionsData, queryClient, stats]);
};
