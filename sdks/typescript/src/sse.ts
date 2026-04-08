import type { ProgressEvent } from "./types/sse.js";

export async function* parseSSEStream(response: Response): AsyncGenerator<ProgressEvent> {
  const body = response.body;
  if (!body) return;

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const json = line.slice(6).trim();
        if (!json) continue;
        try {
          yield JSON.parse(json) as ProgressEvent;
        } catch {
          // skip malformed JSON
        }
      }
    }

    // flush remaining buffer
    if (buffer.startsWith("data: ")) {
      const json = buffer.slice(6).trim();
      if (json) {
        try {
          yield JSON.parse(json) as ProgressEvent;
        } catch {
          // skip
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
