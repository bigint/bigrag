import type { ProgressEvent } from "./types/sse.js";

class SSEParseError extends Error {
  readonly raw: string;
  readonly cause: unknown;
  constructor(raw: string, cause: unknown) {
    super(`SSE parse error: ${cause instanceof Error ? cause.message : String(cause)}`);
    this.name = "SSEParseError";
    this.raw = raw;
    this.cause = cause;
  }
}

export interface SSEFrame {
  event: string;
  data: string;
  id?: string;
  retry?: number;
}

export interface SSEState {
  lastEventId?: string;
  retryMs?: number;
}

export async function* parseSSEFrames(
  response: Response,
  state?: SSEState,
): AsyncGenerator<SSEFrame> {
  const body = response.body;
  if (!body) return;

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "message";
  let dataLines: string[] = [];
  let id: string | undefined;

  const flush = (): SSEFrame | null => {
    const payload = dataLines.join("\n");
    if (!payload || payload === "[DONE]") return null;
    const frame: SSEFrame = { event, data: payload };
    if (id !== undefined) frame.id = id;
    return frame;
  };

  const consumeLine = (rawLine: string): SSEFrame | null => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (line === "") {
      const frame = flush();
      event = "message";
      dataLines = [];
      return frame;
    }
    if (line.startsWith(":")) return null;
    if (line.startsWith("event:")) {
      event = line.slice(6).replace(/^ /, "");
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    } else if (line.startsWith("id:")) {
      id = line.slice(3).replace(/^ /, "");
      if (state) state.lastEventId = id;
    } else if (line.startsWith("retry:")) {
      const ms = Number(line.slice(6).replace(/^ /, ""));
      if (Number.isFinite(ms) && ms >= 0 && state) state.retryMs = ms;
    }
    return null;
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";

      for (const rawLine of lines) {
        const frame = consumeLine(rawLine);
        if (frame) yield frame;
      }
    }

    const tail = buffer.endsWith("\r") ? buffer.slice(0, -1) : buffer;
    if (tail) consumeLine(tail);
    const trailing = flush();
    if (trailing) yield trailing;
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

export async function* parseSSEStream(response: Response): AsyncGenerator<ProgressEvent> {
  for await (const frame of parseSSEFrames(response)) {
    try {
      yield JSON.parse(frame.data) as ProgressEvent;
    } catch (cause) {
      throw new SSEParseError(frame.data, cause);
    }
  }
}
