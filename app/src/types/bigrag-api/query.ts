export type Chunk = {
  id: string;
  text: string;
  document_id: string;
  chunk_index: number;
  metadata: Record<string, unknown>;
};

export type QueryResult = {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  page_no?: number | null;
  char_start?: number | null;
  char_end?: number | null;
  metadata: Record<string, unknown>;
};

export type QueryTimings = {
  embed_ms: number;
  search_ms: number;
  rerank_ms: number;
  total_ms: number;
};

export type QueryResponse = {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
  timings?: QueryTimings;
};
