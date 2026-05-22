import type { MultimodalElementRef } from "./documents.js";
import type { QueryTimings } from "./query.js";

export interface ChatQuestionSuggestionsBody {
  collection: string;
  model?: string | null;
  temperature?: number | null;
}

export interface ChatQuestionSuggestionsResponse {
  collection: string;
  questions: string[];
  generated_at: string | null;
  model: string | null;
}

export interface ChatCreateBody {
  message: string;
  collection: string;
  stream?: boolean;
  model_provider?: "openai" | "openai_compatible";
  model?: string;
  temperature?: number;
  top_k?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
  min_score?: number | null;
  rerank?: boolean | null;
  filters?: Record<string, unknown> | null;
  multimodal?: boolean;
  system_prompt?: string;
  provider_api_key?: string;
  provider_base_url?: string | null;
}

export interface ChatSource {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  document_filename: string | null;
  chunk_index: number | null;
  page_no?: number | null;
  char_start?: number | null;
  char_end?: number | null;
  multimodal_elements: MultimodalElementRef[];
  metadata: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: "complete" | "error";
  error_message: string | null;
  model_provider: string | null;
  model: string | null;
  retrieval: Record<string, unknown>;
  sources: ChatSource[];
  created_at: string;
}

export interface ChatCreateResponse {
  message: ChatMessage;
  assistant_message: ChatMessage;
  sources: ChatSource[];
  timings?: QueryTimings | null;
}

export type ChatStreamEvent =
  | { event: "user_message"; data: ChatMessage }
  | {
      event: "sources";
      data: { collection: string | null; sources: ChatSource[]; timings?: QueryTimings };
    }
  | { event: "delta"; data: { delta: string } }
  | { event: "assistant_message"; data: ChatMessage }
  | { event: "done"; data: Record<string, never> }
  | { event: "error"; data: { error: string } };
