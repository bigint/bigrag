import type { ChatMessage as ServerChatMessage } from "@bigrag/client/browser";
import type { QueryTimings } from "@/types/bigrag";

const timingNumber = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : 0;

export const normalizeTimings = (timings: unknown): QueryTimings | undefined => {
  if (!timings || typeof timings !== "object") return undefined;
  const raw = timings as Record<string, unknown>;
  return {
    embed_ms: timingNumber(raw.embed_ms),
    search_ms: timingNumber(raw.search_ms),
    rerank_ms: timingNumber(raw.rerank_ms),
    cache_ms: timingNumber(raw.cache_ms),
    total_ms: timingNumber(raw.total_ms),
    cache_hit: raw.cache_hit === true,
  };
};

export const timingsFromRetrieval = (message: ServerChatMessage): QueryTimings | undefined => {
  return normalizeTimings(message.retrieval.timings);
};
