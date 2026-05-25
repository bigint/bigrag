export interface CollectionUsage {
  collection: string;
  documents: number;
  chunks: number;
  storage_bytes: number;
  embedding_tokens: number;
  embedding_cost_usd_estimate: number;
  queries: number;
  avg_latency_ms: number;
}

export interface UsageResponse {
  window_days: number;
  queries_total: number;
  queries_per_day_avg: number;
  documents_total: number;
  chunks_total: number;
  storage_bytes_total: number;
  embedding_tokens_total: number;
  embedding_cost_usd_estimate: number;
  avg_latency_ms: number;
  timeline: { date: string; queries: number; avg_latency_ms: number }[];
  by_collection: CollectionUsage[];
}
