import type { ChatSource } from "@bigrag/client/browser";
import type { QueryTimings } from "@/types/bigrag";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: "complete" | "error" | "stopped";
  errorMessage?: string | null;
  meta?: {
    collection: string | null;
    sources: ChatSource[];
    timings?: QueryTimings;
  };
};

export const formatWholeMs = (ms: number) => (ms > 0 && ms < 1 ? "<1ms" : `${Math.round(ms)}ms`);
