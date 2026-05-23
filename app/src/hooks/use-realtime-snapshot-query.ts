import {
  hashKey,
  type QueryClient,
  type QueryFunction,
  type QueryKey,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { realtimeUrl } from "@/config/runtime";

type RealtimeParams = Record<string, string | number | boolean | string[] | null | undefined>;

type SnapshotEvent<T> = {
  generated_at: string;
  id: string;
  payload: T;
  topic: string;
  type: "snapshot";
};

type RealtimeMessage<T> =
  | SnapshotEvent<T>
  | {
      generated_at?: string;
      id?: string;
      message?: string;
      topic?: string;
      type: string;
    };

type RealtimeSnapshotQueryOptions<T> = {
  closeWhen?: (payload: T) => boolean;
  enabled?: boolean;
  firstSnapshotTimeoutMs?: number;
  params?: RealtimeParams;
  pollIntervalMs?: number;
  queryFn: QueryFunction<T, QueryKey>;
  queryKey: QueryKey;
  streamPriority?: "high" | "normal" | "low";
  topic: string;
};

const DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS = 5_000;
const DEFAULT_POLL_INTERVAL_MS = 30_000;
const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1_000;

type MessageListener = (event: RealtimeMessage<unknown>) => void;
type ErrorListener = () => void;

type StreamEntry = {
  errorListeners: Set<ErrorListener>;
  id: string;
  listeners: Set<MessageListener>;
  params: Record<string, string | number | boolean | string[]>;
  refcount: number;
  topic: string;
};

let socket: WebSocket | null = null;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
const streams = new Map<string, StreamEntry>();

const randomId = () => {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return Math.random().toString(36).slice(2);
};

const jitter = (ms: number) => ms * (0.75 + Math.random() * 0.5);

const backoffDelay = (attempt: number) =>
  Math.round(jitter(Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS)));

const compactParams = (params?: RealtimeParams) =>
  Object.fromEntries(
    Object.entries(params ?? {}).filter(([, value]) => value !== undefined && value !== null),
  ) as Record<string, string | number | boolean | string[]>;

const streamKey = (topic: string, params?: RealtimeParams) =>
  `${topic}:${JSON.stringify(compactParams(params))}`;

const streamById = (id: string) => Array.from(streams.values()).find((entry) => entry.id === id);

const send = (message: unknown) => {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify(message));
};

const subscribeEntry = (entry: StreamEntry) => {
  send({ type: "subscribe", id: entry.id, topic: entry.topic, params: entry.params });
};

const dispatchError = () => {
  for (const entry of streams.values()) {
    for (const listener of entry.errorListeners) listener();
  }
};

const openSocket = () => {
  if (socket && socket.readyState !== WebSocket.CLOSED) return;
  socket = new WebSocket(realtimeUrl());

  socket.addEventListener("open", () => {
    reconnectAttempt = 0;
    for (const entry of streams.values()) subscribeEntry(entry);
  });

  socket.addEventListener("message", (event) => {
    let message: RealtimeMessage<unknown>;
    try {
      message = JSON.parse(String(event.data)) as RealtimeMessage<unknown>;
    } catch {
      dispatchError();
      return;
    }
    if (message.type === "heartbeat" || message.type === "pong" || message.type === "subscribed") {
      return;
    }
    if (message.type === "error") {
      const entry = message.id ? streamById(message.id) : undefined;
      const targets = entry ? [entry] : Array.from(streams.values());
      for (const target of targets) {
        for (const listener of target.errorListeners) listener();
      }
      return;
    }
    if (!message.id) return;
    const entry = streamById(message.id);
    if (!entry) return;
    if (message.type === "complete") {
      return;
    }
    for (const listener of entry.listeners) listener(message);
  });

  socket.addEventListener("close", () => {
    socket = null;
    if (streams.size === 0) return;
    dispatchError();
    scheduleReconnect();
  });

  socket.addEventListener("error", () => {
    dispatchError();
  });
};

const scheduleReconnect = () => {
  if (reconnectTimer) return;
  if (streams.size === 0) return;
  if (reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) return;
  const delay = backoffDelay(reconnectAttempt);
  reconnectAttempt += 1;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    openSocket();
  }, delay);
};

const subscribeStream = (
  topic: string,
  params: RealtimeParams | undefined,
  onMessage: MessageListener,
  onError: ErrorListener,
): (() => void) => {
  const key = streamKey(topic, params);
  let entry = streams.get(key);
  let created = false;
  if (!entry) {
    entry = {
      id: randomId(),
      topic,
      params: compactParams(params),
      listeners: new Set(),
      errorListeners: new Set(),
      refcount: 0,
    };
    streams.set(key, entry);
    created = true;
  }
  entry.listeners.add(onMessage);
  entry.errorListeners.add(onError);
  entry.refcount += 1;
  openSocket();
  if (created && socket?.readyState === WebSocket.OPEN) subscribeEntry(entry);

  return () => {
    const current = streams.get(key);
    if (!current) return;
    current.listeners.delete(onMessage);
    current.errorListeners.delete(onError);
    current.refcount = Math.max(0, current.refcount - 1);
    if (current.refcount === 0) {
      send({ type: "unsubscribe", id: current.id });
      streams.delete(key);
      if (streams.size === 0) {
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }
        socket?.close();
        socket = null;
      }
    }
  };
};

export const closeAllRealtimeStreams = () => {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  for (const entry of streams.values()) {
    entry.listeners.clear();
    entry.errorListeners.clear();
    entry.refcount = 0;
  }
  streams.clear();
  socket?.close();
  socket = null;
};

export const useRealtimeSnapshotQuery = <T>({
  closeWhen,
  enabled = true,
  firstSnapshotTimeoutMs = DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS,
  params,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  queryFn,
  queryKey,
  streamPriority: _streamPriority = "normal",
  topic,
}: RealtimeSnapshotQueryOptions<T>) => {
  const queryClient = useQueryClient();
  const queryClientRef = useRef<QueryClient>(queryClient);
  const closeWhenRef = useRef(closeWhen);
  const queryFnRef = useRef(queryFn);
  const fallbackStartedRef = useRef(false);
  const [realtimeUnavailable, setRealtimeUnavailable] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const queryKeyHash = useMemo(() => hashKey(queryKey), [queryKey]);
  const queryKeyRef = useRef(queryKey);
  const paramsHash = useMemo(() => JSON.stringify(compactParams(params)), [params]);

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

    const fetchFallback = () => {
      if (fallbackStartedRef.current) return;
      fallbackStartedRef.current = true;
      setRealtimeUnavailable(true);
      void queryClientRef.current.invalidateQueries({ queryKey: queryKeyRef.current });
    };

    const firstSnapshotTimer = window.setTimeout(() => {
      if (!sawSnapshot) fetchFallback();
    }, firstSnapshotTimeoutMs);

    const handleMessage = (message: RealtimeMessage<unknown>) => {
      if (message.type !== "snapshot") return;
      const snapshot = message as SnapshotEvent<T>;
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
    };

    const handleError = () => {
      failureCount += 1;
      if (failureCount >= MAX_RECONNECT_ATTEMPTS) {
        fetchFallback();
        setStreaming(false);
      }
    };

    const unsubscribe = subscribeStream(
      topic,
      JSON.parse(paramsHash) as RealtimeParams,
      handleMessage,
      handleError,
    );

    return () => {
      window.clearTimeout(firstSnapshotTimer);
      if (!unsubscribed) unsubscribe();
      setStreaming(false);
    };
  }, [enabled, firstSnapshotTimeoutMs, paramsHash, queryKeyHash, topic]);

  return { ...query, realtimeUnavailable, streaming };
};
