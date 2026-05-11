import type {
  QueryResult as SdkQueryResult,
  QueryTimings as SdkQueryTimings,
} from "@bigrag/client";

export type Chunk = {
  id: string;
  text: string;
  document_id: string;
  chunk_index: number;
  metadata: Record<string, unknown>;
};

export type QueryResult = SdkQueryResult & {
  page_no?: number | null;
  char_start?: number | null;
  char_end?: number | null;
};

export type QueryTimings = Required<SdkQueryTimings>;
