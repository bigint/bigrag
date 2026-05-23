import { type RequestClient, USER_AGENT } from "./core.js";
import { APIConnectionError } from "./errors.js";
import type { RealtimeMessage } from "./types/index.js";

type AnySocket = {
  addEventListener?: (event: string, handler: (event: unknown) => void, options?: unknown) => void;
  close: () => void;
  on?: (event: string, handler: (...args: unknown[]) => void) => void;
  readyState?: number;
  send: (data: string) => void;
};

const OPEN = 1;

class AsyncQueue<T> {
  private readonly items: T[] = [];
  private readonly waiters: ((value: T | undefined) => void)[] = [];
  private closed = false;

  push(item: T): void {
    const waiter = this.waiters.shift();
    if (waiter) {
      waiter(item);
      return;
    }
    this.items.push(item);
  }

  close(): void {
    this.closed = true;
    for (const waiter of this.waiters.splice(0)) waiter(undefined);
  }

  next(): Promise<T | undefined> {
    const item = this.items.shift();
    if (item !== undefined) return Promise.resolve(item);
    if (this.closed) return Promise.resolve(undefined);
    return new Promise((resolve) => this.waiters.push(resolve));
  }
}

export class BigRAGRealtimeConnection {
  private socket: AnySocket | null = null;
  private connecting: Promise<void> | null = null;
  private closing = false;
  private closedError: Error | null = null;
  private readonly queues = new Map<string, AsyncQueue<RealtimeMessage<unknown>>>();

  constructor(private readonly client: RequestClient) {}

  async connect(): Promise<void> {
    if (this.socket?.readyState === OPEN) return;
    if (this.connecting) return this.connecting;
    this.connecting = this.open();
    try {
      await this.connecting;
    } finally {
      this.connecting = null;
    }
  }

  async close(): Promise<void> {
    this.closing = true;
    for (const queue of this.queues.values()) queue.close();
    this.queues.clear();
    this.socket?.close();
    this.socket = null;
  }

  async *subscribe<T = unknown>(
    topic: string,
    params: Record<string, unknown> = {},
  ): AsyncGenerator<RealtimeMessage<T>> {
    await this.connect();
    const id = randomId();
    const queue = new AsyncQueue<RealtimeMessage<unknown>>();
    this.queues.set(id, queue);
    this.send({ type: "subscribe", id, topic, params: compactParams(params) });
    try {
      while (true) {
        const message = await queue.next();
        if (!message) {
          if (this.closedError) throw this.closedError;
          return;
        }
        yield message as RealtimeMessage<T>;
        if (message.type === "complete" || message.type === "error") return;
      }
    } finally {
      this.send({ type: "unsubscribe", id });
      this.queues.delete(id);
      queue.close();
    }
  }

  private async open(): Promise<void> {
    const { Socket, supportsHeaders } = await websocketConstructor(this.client.apiKey !== "");
    if (this.client.apiKey && !supportsHeaders) {
      throw new APIConnectionError(
        "Browser WebSocket cannot send the Authorization header required for API-key auth; use session-cookie auth or a collection realtime token.",
      );
    }
    const url = realtimeUrl(this.client.baseUrl);
    const headers: Record<string, string> = { "User-Agent": USER_AGENT };
    if (this.client.apiKey) headers.Authorization = `Bearer ${this.client.apiKey}`;
    const socket = (
      supportsHeaders ? new Socket(url, undefined, { headers }) : new Socket(url)
    ) as AnySocket;
    this.socket = socket;
    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const done = (fn: () => void) => {
        if (settled) return;
        settled = true;
        fn();
      };
      on(socket, "open", () => done(resolve));
      on(socket, "error", (event) =>
        done(() => reject(new APIConnectionError(websocketErrorMessage(event)))),
      );
      on(socket, "message", (event) => this.handleMessage(event));
      on(socket, "close", () => this.handleClose());
    });
  }

  private send(message: unknown): void {
    if (!this.socket || this.socket.readyState !== OPEN) return;
    this.socket.send(JSON.stringify(message));
  }

  private handleMessage(event: unknown): void {
    const raw = messageData(event);
    if (raw === undefined) return;
    let message: RealtimeMessage<unknown>;
    try {
      message = JSON.parse(raw) as RealtimeMessage<unknown>;
    } catch {
      return;
    }
    if (message.type === "heartbeat" || message.type === "pong" || message.type === "subscribed") {
      return;
    }
    if (!message.id) return;
    this.queues.get(message.id)?.push(message);
  }

  private handleClose(): void {
    this.socket = null;
    if (!this.closing) {
      this.closedError = new APIConnectionError("Realtime connection closed unexpectedly");
    }
    for (const queue of this.queues.values()) queue.close();
    this.queues.clear();
  }
}

export class RealtimeResource {
  constructor(private readonly client: RequestClient) {}

  connect(): BigRAGRealtimeConnection {
    return new BigRAGRealtimeConnection(this.client);
  }

  async *subscribe<T = unknown>(
    topic: string,
    params: Record<string, unknown> = {},
  ): AsyncGenerator<RealtimeMessage<T>> {
    const connection = this.connect();
    try {
      yield* connection.subscribe<T>(topic, params);
    } finally {
      await connection.close();
    }
  }
}

const randomId = () => {
  const crypto = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (crypto?.randomUUID) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
};

const websocketErrorMessage = (event: unknown): string => {
  if (event && typeof event === "object") {
    const candidate = event as { message?: unknown; error?: { message?: unknown } };
    if (typeof candidate.message === "string") return candidate.message;
    if (candidate.error && typeof candidate.error.message === "string") {
      return candidate.error.message;
    }
  }
  return "WebSocket connection failed";
};

const compactParams = (params: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined));

const realtimeUrl = (baseUrl: string) => {
  const url = new URL("/v1/realtime", `${baseUrl}/`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
};

const websocketConstructor = async (needsHeaders: boolean) => {
  if (needsHeaders && !isBrowserRuntime()) return websocketModuleConstructor();
  const globalSocket = (globalThis as { WebSocket?: unknown }).WebSocket;
  if (globalSocket) {
    return {
      Socket: globalSocket as new (...args: unknown[]) => AnySocket,
      supportsHeaders: false,
    };
  }
  return websocketModuleConstructor();
};

const websocketModuleConstructor = async () => {
  const dynamicImport = new Function("specifier", "return import(specifier)") as (
    specifier: string,
  ) => Promise<{ WebSocket?: new (...args: unknown[]) => AnySocket; default?: unknown }>;
  const module = await dynamicImport("ws");
  return {
    Socket: (module.WebSocket ?? module.default) as new (...args: unknown[]) => AnySocket,
    supportsHeaders: true,
  };
};

const isBrowserRuntime = () =>
  (globalThis as { window?: unknown }).window !== undefined &&
  (globalThis as { window?: unknown }).window === globalThis;

const on = (socket: AnySocket, event: string, handler: (...args: unknown[]) => void) => {
  if (socket.addEventListener) {
    socket.addEventListener(event, (payload) => handler(payload));
    return;
  }
  socket.on?.(event, handler);
};

const messageData = (event: unknown): string | undefined => {
  if (typeof event === "string") return event;
  if (event instanceof Uint8Array) return new TextDecoder().decode(event);
  if (event && typeof event === "object" && "data" in event) {
    const data = (event as { data?: unknown }).data;
    if (typeof data === "string") return data;
    if (data instanceof Uint8Array) return new TextDecoder().decode(data);
  }
  return undefined;
};
