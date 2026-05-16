import { type QueryFunction, type QueryKey, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { apiUrl } from "@/config/runtime";

type SnapshotEvent<T> = {
  topic: string;
  payload: T;
  generated_at: string;
};

type SseSnapshotQueryOptions<T> = {
  closeWhen?: (payload: T) => boolean;
  enabled?: boolean;
  firstSnapshotTimeoutMs?: number;
  path: string;
  pollIntervalMs?: number;
  queryFn: QueryFunction<T, QueryKey>;
  queryKey: QueryKey;
  streamPriority?: "high" | "normal" | "low";
};

const eventSourcePath = (path: string) => apiUrl(path);
const MAX_ACTIVE_SSE_STREAMS = 2;
const DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS = 5_000;
const DEFAULT_POLL_INTERVAL_MS = 30_000;

let activeSseStreams = 0;

export const useSseSnapshotQuery = <T>({
  closeWhen,
  enabled = true,
  firstSnapshotTimeoutMs = DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS,
  path,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  queryFn,
  queryKey,
  streamPriority = "normal",
}: SseSnapshotQueryOptions<T>) => {
  const queryClient = useQueryClient();
  const closeWhenRef = useRef(closeWhen);
  const queryFnRef = useRef(queryFn);
  const fallbackStartedRef = useRef(true);
  const [realtimeUnavailable, setRealtimeUnavailable] = useState(false);
  const [streaming, setStreaming] = useState(false);

  useEffect(() => {
    closeWhenRef.current = closeWhen;
  }, [closeWhen]);

  useEffect(() => {
    queryFnRef.current = queryFn;
  }, [queryFn]);

  const query = useQuery<T>({
    enabled,
    queryFn: (context) => queryFnRef.current(context),
    queryKey,
    refetchInterval: realtimeUnavailable ? pollIntervalMs : false,
    retry: false,
  });

  useEffect(() => {
    if (!enabled) {
      setStreaming(false);
      setRealtimeUnavailable(false);
      return;
    }

    if (streamPriority === "low" || activeSseStreams >= MAX_ACTIVE_SSE_STREAMS) {
      setStreaming(false);
      setRealtimeUnavailable(true);
      return;
    }

    fallbackStartedRef.current = false;
    setRealtimeUnavailable(false);
    activeSseStreams += 1;
    const source = new EventSource(eventSourcePath(path), { withCredentials: true });
    let closed = false;
    let sawSnapshot = false;
    let released = false;
    const firstSnapshotTimer = window.setTimeout(() => {
      if (!sawSnapshot) {
        fetchFallback();
        close();
      }
    }, firstSnapshotTimeoutMs);

    const releaseSlot = () => {
      if (released) return;
      released = true;
      activeSseStreams = Math.max(0, activeSseStreams - 1);
    };

    const close = () => {
      if (closed) return;
      closed = true;
      window.clearTimeout(firstSnapshotTimer);
      releaseSlot();
      source.close();
      setStreaming(false);
    };

    const fetchFallback = () => {
      if (fallbackStartedRef.current) return;
      fallbackStartedRef.current = true;
      setRealtimeUnavailable(true);
      void queryClient.invalidateQueries({ queryKey });
    };

    source.onopen = () => {
      if (!closed) setStreaming(true);
    };

    source.addEventListener("snapshot", (event) => {
      try {
        const snapshot = JSON.parse((event as MessageEvent<string>).data) as SnapshotEvent<T>;
        sawSnapshot = true;
        queryClient.setQueryData(queryKey, snapshot.payload);
        if (closeWhenRef.current?.(snapshot.payload)) {
          close();
        }
      } catch {
        fetchFallback();
        close();
      }
    });

    source.addEventListener("error", () => {
      fetchFallback();
      close();
    });

    source.onerror = () => {
      if (!closed) {
        fetchFallback();
        close();
      }
    };

    return close;
  }, [enabled, firstSnapshotTimeoutMs, path, queryClient, queryKey, streamPriority]);

  return { ...query, realtimeUnavailable, streaming };
};
