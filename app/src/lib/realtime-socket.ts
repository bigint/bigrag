import { realtimeUrl } from "@/config/runtime";

export type RealtimeParams = Record<
  string,
  string | number | boolean | string[] | null | undefined
>;

export type SnapshotEvent<T> = {
  generated_at: string;
  id: string;
  payload: T;
  topic: string;
  type: "snapshot";
};

export type RealtimeMessage<T> =
  | SnapshotEvent<T>
  | {
      generated_at?: string;
      id?: string;
      message?: string;
      topic?: string;
      type: string;
      version?: number;
    };

export const DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS = 5_000;
export const DEFAULT_POLL_INTERVAL_MS = 30_000;
export const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1_000;
const WS_POLICY_VIOLATION = 1008;

export type ErrorKind = "transport" | "subscription";
export type MessageListener = (event: RealtimeMessage<unknown>) => void;
export type ErrorListener = (kind: ErrorKind) => void;

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

export const compactParams = (params?: RealtimeParams) =>
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

export const subscribeStream = (
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
