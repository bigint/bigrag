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

export type RealtimeParams = Record<
  string,
  string | number | boolean | string[] | null | undefined
>;

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
      version?: number;
    };

type RealtimeSnapshotQueryOptions<T> = {
  closeWhen?: (payload: T) => boolean;
  enabled?: boolean;
  firstSnapshotTimeoutMs?: number;
  params?: RealtimeParams;
  pollIntervalMs?: number;
  queryFn: QueryFunction<T, QueryKey>;
  queryKey: QueryKey;
  topic: string;
};

export type RealtimeSnapshotSubscription = {
  key: string;
  params?: RealtimeParams;
  topic: string;
};

type RealtimeSnapshotSubscriptionsOptions<T> = {
  enabled?: boolean;
  firstSnapshotTimeoutMs?: number;
  onSnapshot: (payload: T, subscription: RealtimeSnapshotSubscription) => void;
  onUnavailable?: (subscription: RealtimeSnapshotSubscription) => void;
  pollIntervalMs?: number;
  subscriptions: RealtimeSnapshotSubscription[];
};

const DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS = 5_000;
const DEFAULT_POLL_INTERVAL_MS = 30_000;
const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1_000;
const WS_POLICY_VIOLATION = 1008;

type ErrorKind = "transport" | "subscription";
type MessageListener = (event: RealtimeMessage<unknown>) => void;
type ErrorListener = (kind: ErrorKind) => void;

type StreamEntry = {
  completed: boolean;
  errorListeners: Set<ErrorListener>;
  id: string;
  listeners: Set<MessageListener>;
  params: Record<string, string | number | boolean | string[]>;
  refcount: number;
  topic: string;
};

let socket: WebSocket | null = null;
let socketGeneration = 0;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
const streams = new Map<string, StreamEntry>();
const streamsById = new Map<string, StreamEntry>();

const randomId = () => {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
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

const send = (message: unknown) => {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify(message));
};

const subscribeEntry = (entry: StreamEntry) => {
  if (entry.completed) return;
  send({ type: "subscribe", id: entry.id, topic: entry.topic, params: entry.params });
};

const dispatchError = (kind: ErrorKind) => {
  for (const entry of streams.values()) {
    for (const listener of entry.errorListeners) listener(kind);
  }
};

const closeSocket = () => {
  const current = socket;
  socket = null;
  socketGeneration += 1;
  current?.close();
};

const openSocket = () => {
  if (socket && socket.readyState !== WebSocket.CLOSING && socket.readyState !== WebSocket.CLOSED) {
    return;
  }
  const currentSocket = new WebSocket(realtimeUrl());
  socket = currentSocket;
  const generation = socketGeneration + 1;
  socketGeneration = generation;
  const isCurrentSocket = () => socket === currentSocket && socketGeneration === generation;

  currentSocket.addEventListener("open", () => {
    if (!isCurrentSocket()) return;
    reconnectAttempt = 0;
    for (const entry of streams.values()) subscribeEntry(entry);
  });

  currentSocket.addEventListener("message", (event) => {
    if (!isCurrentSocket()) return;
    let message: RealtimeMessage<unknown>;
    try {
      message = JSON.parse(String(event.data)) as RealtimeMessage<unknown>;
    } catch {
      return;
    }
    if (message.type === "heartbeat" || message.type === "pong" || message.type === "subscribed") {
      return;
    }
    if (message.type === "error") {
      const entry = message.id ? streamsById.get(message.id) : undefined;
      const targets = entry ? [entry] : Array.from(streams.values());
      for (const target of targets) {
        for (const listener of target.errorListeners) listener("subscription");
      }
      return;
    }
    if (!message.id) return;
    const entry = streamsById.get(message.id);
    if (!entry) return;
    if (message.type === "complete") {
      entry.completed = true;
    }
    for (const listener of entry.listeners) listener(message);
  });

  currentSocket.addEventListener("close", (event) => {
    if (!isCurrentSocket()) return;
    socket = null;
    if (streams.size === 0) return;
    dispatchError("transport");
    if (event.code === WS_POLICY_VIOLATION) return;
    scheduleReconnect();
  });

  currentSocket.addEventListener("error", () => {
    if (!isCurrentSocket()) return;
    dispatchError("transport");
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

const resumeRealtime = () => {
  if (streams.size === 0) return;
  if (socket && socket.readyState !== WebSocket.CLOSING && socket.readyState !== WebSocket.CLOSED) {
    return;
  }
  reconnectAttempt = 0;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  openSocket();
};

if (typeof window !== "undefined") {
  window.addEventListener("online", resumeRealtime);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") resumeRealtime();
  });
}

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
      completed: false,
    };
    streams.set(key, entry);
    streamsById.set(entry.id, entry);
    created = true;
  }
  entry.listeners.add(onMessage);
  entry.errorListeners.add(onError);
  entry.refcount += 1;
  reconnectAttempt = 0;
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
      streamsById.delete(current.id);
      if (streams.size === 0 && reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    }
  };
};

export const useRealtimeSnapshotSubscriptions = <T>({
  enabled = true,
  firstSnapshotTimeoutMs = DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS,
  onSnapshot,
  onUnavailable,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  subscriptions,
}: RealtimeSnapshotSubscriptionsOptions<T>) => {
  const onSnapshotRef = useRef(onSnapshot);
  const onUnavailableRef = useRef(onUnavailable);
  const [realtimeUnavailable, setRealtimeUnavailable] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const normalizedSubscriptions = useMemo(
    () =>
      subscriptions.map((subscription) => ({
        ...subscription,
        params: compactParams(subscription.params),
      })),
    [subscriptions],
  );
  const subscriptionsHash = useMemo(
    () => JSON.stringify(normalizedSubscriptions),
    [normalizedSubscriptions],
  );

  useEffect(() => {
    onSnapshotRef.current = onSnapshot;
  }, [onSnapshot]);

  useEffect(() => {
    onUnavailableRef.current = onUnavailable;
  }, [onUnavailable]);

  useEffect(() => {
    const activeSubscriptions = JSON.parse(subscriptionsHash) as RealtimeSnapshotSubscription[];
    if (!enabled || activeSubscriptions.length === 0) {
      setStreaming(false);
      setRealtimeUnavailable(false);
      return;
    }

    setRealtimeUnavailable(false);
    setStreaming(true);

    const activeKeys = new Set(activeSubscriptions.map((subscription) => subscription.key));
    const fallbackKeys = new Set<string>();
    const failureCounts = new Map<string, number>();
    const pollTimers = new Map<string, number>();
    const snapshotKeys = new Set<string>();
    const timers: number[] = [];
    const unsubscribes: (() => void)[] = [];

    const clearPoll = (key: string) => {
      const timer = pollTimers.get(key);
      if (timer === undefined) return;
      window.clearInterval(timer);
      pollTimers.delete(key);
    };

    const markComplete = (key: string) => {
      activeKeys.delete(key);
      clearPoll(key);
      if (activeKeys.size === 0) setStreaming(false);
    };

    const fallback = (subscription: RealtimeSnapshotSubscription) => {
      if (fallbackKeys.has(subscription.key)) return;
      fallbackKeys.add(subscription.key);
      setRealtimeUnavailable(true);
      onUnavailableRef.current?.(subscription);
      if (pollIntervalMs > 0) {
        pollTimers.set(
          subscription.key,
          window.setInterval(() => onUnavailableRef.current?.(subscription), pollIntervalMs),
        );
      }
    };

    for (const subscription of activeSubscriptions) {
      const timer = window.setTimeout(() => {
        if (!snapshotKeys.has(subscription.key)) fallback(subscription);
      }, firstSnapshotTimeoutMs);
      timers.push(timer);

      const handleMessage = (message: RealtimeMessage<unknown>) => {
        if (message.type === "complete") {
          markComplete(subscription.key);
          return;
        }
        if (message.type !== "snapshot") return;
        const snapshot = message as SnapshotEvent<T>;
        snapshotKeys.add(subscription.key);
        failureCounts.set(subscription.key, 0);
        fallbackKeys.delete(subscription.key);
        clearPoll(subscription.key);
        if (fallbackKeys.size === 0) setRealtimeUnavailable(false);
        onSnapshotRef.current(snapshot.payload, subscription);
      };

      const handleError = (kind: ErrorKind) => {
        if (kind === "transport") {
          fallback(subscription);
          return;
        }
        const failureCount = (failureCounts.get(subscription.key) ?? 0) + 1;
        failureCounts.set(subscription.key, failureCount);
        if (failureCount >= MAX_RECONNECT_ATTEMPTS) {
          fallback(subscription);
          markComplete(subscription.key);
        }
      };

      unsubscribes.push(
        subscribeStream(subscription.topic, subscription.params, handleMessage, handleError),
      );
    }

    return () => {
      for (const timer of timers) window.clearTimeout(timer);
      for (const timer of pollTimers.values()) window.clearInterval(timer);
      for (const unsubscribe of unsubscribes) unsubscribe();
      setStreaming(false);
    };
  }, [enabled, firstSnapshotTimeoutMs, pollIntervalMs, subscriptionsHash]);

  return { realtimeUnavailable, streaming };
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
  streamsById.clear();
  closeSocket();
};

export const useRealtimeSnapshotQuery = <T>({
  closeWhen,
  enabled = true,
  firstSnapshotTimeoutMs = DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS,
  params,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  queryFn,
  queryKey,
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
      if (message.type === "complete") {
        setStreaming(false);
        return;
      }
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

    const handleError = (kind: ErrorKind) => {
      if (kind === "transport") {
        fetchFallback();
        return;
      }
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
