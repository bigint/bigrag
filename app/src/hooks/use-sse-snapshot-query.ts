"use client";

import { type QueryFunction, type QueryKey, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

type SnapshotEvent<T> = {
  topic: string;
  payload: T;
  generated_at: string;
};

type SseSnapshotQueryOptions<T> = {
  closeWhen?: (payload: T) => boolean;
  enabled?: boolean;
  path: string;
  queryFn: QueryFunction<T, QueryKey>;
  queryKey: QueryKey;
};

const eventSourcePath = (path: string) => `/api/bigrag/${path.replace(/^\/+/, "")}`;

export const useSseSnapshotQuery = <T>({
  closeWhen,
  enabled = true,
  path,
  queryFn,
  queryKey,
}: SseSnapshotQueryOptions<T>) => {
  const queryClient = useQueryClient();
  const closeWhenRef = useRef(closeWhen);
  const queryFnRef = useRef(queryFn);
  const fallbackStartedRef = useRef(false);
  const [streaming, setStreaming] = useState(false);

  useEffect(() => {
    closeWhenRef.current = closeWhen;
  }, [closeWhen]);

  useEffect(() => {
    queryFnRef.current = queryFn;
  }, [queryFn]);

  const query = useQuery<T>({
    enabled: false,
    queryFn: (context) => queryFnRef.current(context),
    queryKey,
    retry: false,
  });

  useEffect(() => {
    if (!enabled) {
      setStreaming(false);
      return;
    }

    fallbackStartedRef.current = false;
    const source = new EventSource(eventSourcePath(path));
    let closed = false;

    const close = () => {
      closed = true;
      source.close();
      setStreaming(false);
    };

    const fetchFallback = () => {
      if (fallbackStartedRef.current) return;
      if (queryClient.getQueryData(queryKey) !== undefined) return;
      fallbackStartedRef.current = true;
      void queryClient.fetchQuery({
        queryFn: (context) => queryFnRef.current(context),
        queryKey,
      });
    };

    source.onopen = () => {
      if (!closed) setStreaming(true);
    };

    source.addEventListener("snapshot", (event) => {
      const snapshot = JSON.parse((event as MessageEvent<string>).data) as SnapshotEvent<T>;
      queryClient.setQueryData(queryKey, snapshot.payload);
      if (closeWhenRef.current?.(snapshot.payload)) {
        close();
      }
    });

    source.addEventListener("error", (event) => {
      if ("data" in event && typeof event.data === "string" && event.data) {
        fetchFallback();
      }
    });

    source.onerror = () => {
      if (!closed) {
        setStreaming(false);
        fetchFallback();
      }
    };

    return close;
  }, [enabled, path, queryClient, queryKey]);

  return { ...query, streaming };
};
