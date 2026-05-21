import {
  hashKey,
  type QueryClient,
  type QueryFunction,
  type QueryKey,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
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
const DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS = 5_000;
const DEFAULT_POLL_INTERVAL_MS = 30_000;
const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1_000;

type MessageListener = (event: MessageEvent<string>) => void;
type ErrorListener = (event: Event) => void;

type StreamEntry = {
  es: EventSource;
  listeners: Set<MessageListener>;
  errorListeners: Set<ErrorListener>;
  refcount: number;
  reconnectAttempt: number;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
};

const streams = new Map<string, StreamEntry>();

const jitter = (ms: number) => ms * (0.75 + Math.random() * 0.5);

const backoffDelay = (attempt: number) =>
  Math.round(jitter(Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS)));

const dispatchError = (entry: StreamEntry, event: Event) => {
  for (const listener of entry.errorListeners) listener(event);
};

const openStream = (path: string, entry: StreamEntry) => {
  const url = eventSourcePath(path);
  const es = new EventSource(url, { withCredentials: true });
  entry.es = es;

  es.addEventListener("snapshot", (event) => {
    entry.reconnectAttempt = 0;
    for (const listener of entry.listeners) listener(event as MessageEvent<string>);
  });

  es.addEventListener("error", (event) => {
    dispatchError(entry, event);
    scheduleReconnect(path, entry);
  });
};

const scheduleReconnect = (path: string, entry: StreamEntry) => {
  if (entry.reconnectTimer) return;
  if (entry.refcount === 0) return;
  if (entry.reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) return;
  try {
    entry.es.close();
  } catch {}
  const delay = backoffDelay(entry.reconnectAttempt);
  entry.reconnectAttempt += 1;
  entry.reconnectTimer = setTimeout(() => {
    entry.reconnectTimer = null;
    if (entry.refcount === 0) return;
    openStream(path, entry);
  }, delay);
};

const subscribeStream = (
  path: string,
  onMessage: MessageListener,
  onError: ErrorListener,
): (() => void) => {
  let entry = streams.get(path);
  if (!entry) {
    entry = {
      es: null as unknown as EventSource,
      listeners: new Set(),
      errorListeners: new Set(),
      refcount: 0,
      reconnectAttempt: 0,
      reconnectTimer: null,
    };
    streams.set(path, entry);
    openStream(path, entry);
  }
  entry.listeners.add(onMessage);
  entry.errorListeners.add(onError);
  entry.refcount += 1;

  if (!entry.es || entry.es.readyState === EventSource.CLOSED) {
    entry.reconnectAttempt = 0;
    if (entry.reconnectTimer) {
      clearTimeout(entry.reconnectTimer);
      entry.reconnectTimer = null;
    }
    openStream(path, entry);
  }

  return () => {
    const current = streams.get(path);
    if (!current) return;
    current.listeners.delete(onMessage);
    current.errorListeners.delete(onError);
    current.refcount = Math.max(0, current.refcount - 1);
    if (current.refcount === 0) {
      if (current.reconnectTimer) {
        clearTimeout(current.reconnectTimer);
        current.reconnectTimer = null;
      }
      try {
        current.es.close();
      } catch {}
      streams.delete(path);
    }
  };
};

export const closeAllSseStreams = () => {
  for (const [path, entry] of streams) {
    if (entry.reconnectTimer) {
      clearTimeout(entry.reconnectTimer);
      entry.reconnectTimer = null;
    }
    try {
      entry.es.close();
    } catch {}
    entry.listeners.clear();
    entry.errorListeners.clear();
    entry.refcount = 0;
    streams.delete(path);
  }
};

export const useSseSnapshotQuery = <T>({
  closeWhen,
  enabled = true,
  firstSnapshotTimeoutMs = DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS,
  path,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  queryFn,
  queryKey,
  streamPriority: _streamPriority = "normal",
}: SseSnapshotQueryOptions<T>) => {
  const queryClient = useQueryClient();
  const queryClientRef = useRef<QueryClient>(queryClient);
  const closeWhenRef = useRef(closeWhen);
  const queryFnRef = useRef(queryFn);
  const fallbackStartedRef = useRef(false);
  const [realtimeUnavailable, setRealtimeUnavailable] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const queryKeyHash = useMemo(() => hashKey(queryKey), [queryKey]);
  const queryKeyRef = useRef(queryKey);

  useEffect(() => {
    queryClientRef.current = queryClient;
  }, [queryClient]);

  useEffect(() => {
    closeWhenRef.current = closeWhen;
  }, [closeWhen]);

  useEffect(() => {
    queryFnRef.current = queryFn;
  }, [queryFn]);

  useEffect(() => {
    queryKeyRef.current = queryKey;
  }, [queryKey]);

  const query = useQuery<T>({
    enabled,
    queryFn: (context) => queryFnRef.current(context),
    queryKey,
    refetchInterval: (q) => {
      if (q.state.data != null && closeWhenRef.current?.(q.state.data as T)) return false;
      return realtimeUnavailable ? pollIntervalMs : false;
    },
    retry: false,
  });

  useEffect(() => {
    void queryKeyHash;
    if (!enabled) {
      setStreaming(false);
      setRealtimeUnavailable(false);
      return;
    }

    fallbackStartedRef.current = false;
    setRealtimeUnavailable(false);
    setStreaming(true);

    let sawSnapshot = false;
    let unsubscribed = false;
    let failureCount = 0;

    const firstSnapshotTimer = window.setTimeout(() => {
      if (!sawSnapshot) {
        fetchFallback();
      }
    }, firstSnapshotTimeoutMs);

    const fetchFallback = () => {
      if (fallbackStartedRef.current) return;
      fallbackStartedRef.current = true;
      setRealtimeUnavailable(true);
      void queryClientRef.current.invalidateQueries({ queryKey: queryKeyRef.current });
    };

    const handleMessage = (event: MessageEvent<string>) => {
      try {
        const snapshot = JSON.parse(event.data) as SnapshotEvent<T>;
        sawSnapshot = true;
        failureCount = 0;
        setRealtimeUnavailable(false);
        fallbackStartedRef.current = false;
        queryClientRef.current.setQueryData(queryKeyRef.current, snapshot.payload);
        if (snapshot.payload != null && closeWhenRef.current?.(snapshot.payload)) {
          unsubscribe();
          unsubscribed = true;
          setStreaming(false);
        }
      } catch {
        fetchFallback();
      }
    };

    const handleError = () => {
      failureCount += 1;
      if (failureCount >= MAX_RECONNECT_ATTEMPTS) {
        fetchFallback();
        setStreaming(false);
      }
    };

    const unsubscribe = subscribeStream(path, handleMessage, handleError);

    return () => {
      window.clearTimeout(firstSnapshotTimer);
      if (!unsubscribed) unsubscribe();
      setStreaming(false);
    };
  }, [enabled, firstSnapshotTimeoutMs, path, queryKeyHash]);

  return { ...query, realtimeUnavailable, streaming };
};
