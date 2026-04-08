/** Statistics for a single time period. */
export interface PeriodStats {
  query_count: number;
  avg_latency_ms: number;
  avg_score: number;
  avg_result_count: number;
}

/** A frequently-issued query with its count. */
export interface TopQuery {
  query: string;
  count: number;
}

/** Analytics overview for a collection covering multiple time windows. */
export interface AnalyticsResponse {
  collection: string;
  period_24h: PeriodStats;
  period_7d: PeriodStats;
  period_30d: PeriodStats;
  top_queries: TopQuery[];
}
