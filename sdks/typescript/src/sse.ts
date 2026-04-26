import type { ProgressEvent } from "./types/sse.js";

export class SSEParseError extends Error {
  readonly raw: string;
  readonly cause: unknown;
  constructor(raw: string, cause: unknown) {
    super(`SSE parse error: ${cause instanceof Error ? cause.message : String(cause)}`);
    this.name = "SSEParseError";
    this.raw = raw;
    this.cause = cause;
  }
}

const decodeEvent = (dataLines: string[]): ProgressEvent | null => {
  if (dataLines.length === 0) return null;
  const raw = dataLines.join("\n");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ProgressEvent;
  } catch (cause) {
    throw new SSEParseError(raw, cause);
  }
};

export async function* parseSSEStream(response: Response): AsyncGenerator<ProgressEvent> {
  const body = response.body;
  if (!body) return;

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let dataLines: string[] = [];

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const rawLine of lines) {
        const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
        if (line === "") {
          const evt = decodeEvent(dataLines);
          dataLines = [];
          if (evt !== null) yield evt;
          continue;
        }
        if (line.startsWith(":")) continue;
        if (line.startsWith("data:")) {
          const value = line.slice(5).startsWith(" ") ? line.slice(6) : line.slice(5);
          dataLines.push(value);
        }
      }
    }

    const tail = buffer.endsWith("\r") ? buffer.slice(0, -1) : buffer;
    if (tail.startsWith("data:")) {
      const value = tail.slice(5).startsWith(" ") ? tail.slice(6) : tail.slice(5);
      dataLines.push(value);
    }
    const evt = decodeEvent(dataLines);
    if (evt !== null) yield evt;
  } finally {
    reader.releaseLock();
  }
}
