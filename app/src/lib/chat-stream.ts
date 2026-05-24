import type { ChatCreateBody, ChatMessage, ChatSource } from "@bigrag/client";
import { apiUrl } from "@/config/runtime";
import type { QueryTimings } from "@/types/bigrag";

type ChatStreamEvent =
  | { event: "user_message"; data: ChatMessage }
  | {
      event: "sources";
      data: { collection: string | null; sources: ChatSource[]; timings?: QueryTimings };
    }
  | { event: "delta"; data: { delta: string } }
  | { event: "assistant_message"; data: ChatMessage }
  | { event: "done"; data: Record<string, never> }
  | { event: "error"; data: { error: string } };

type StreamOptions = {
  body: ChatCreateBody;
  signal?: AbortSignal;
  onEvent: (event: ChatStreamEvent) => void;
};

class ChatStreamError extends Error {}

export const streamChat = async (opts: StreamOptions): Promise<void> => {
  const res = await fetch(apiUrl("v1/chat"), {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ...opts.body, stream: true }),
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    let detail = "Chat request failed";
    try {
      const err = (await res.json()) as { detail?: string };
      if (err.detail) detail = err.detail;
    } catch {
      detail = `${res.status} ${res.statusText}`;
    }
    throw new ChatStreamError(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;

  try {
    while (!finished) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const parsed = parseFrame(frame);
        if (!parsed) continue;
        if ("done" in parsed) {
          finished = true;
          continue;
        }
        opts.onEvent(parsed.event);
      }
    }
    buffer += decoder.decode();
    if (!finished && buffer.trim()) {
      const parsed = parseFrame(buffer);
      if (parsed && !("done" in parsed)) {
        opts.onEvent(parsed.event);
      }
    }
  } finally {
    reader.releaseLock();
  }
};

const parseFrame = (frame: string): { done: true } | { event: ChatStreamEvent } | null => {
  let eventName = "message";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) {
      eventName = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      data.push(line.slice(6));
    }
  }
  const payload = data.join("\n");
  if (!payload) return null;
  if (payload === "[DONE]") return { done: true };
  try {
    return {
      event: {
        event: eventName,
        data: JSON.parse(payload) as unknown,
      } as ChatStreamEvent,
    };
  } catch {
    return null;
  }
};
