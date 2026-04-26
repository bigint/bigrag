export interface PeriodStats {
  query_count: number;
  avg_latency_ms: number;
  avg_score: number;
  avg_result_count: number;
}

export interface TopQuery {
  query: string;
  count: number;
}

export interface AnalyticsResponse {
  collection: string;
  period_24h: PeriodStats;
  period_7d: PeriodStats;
  period_30d: PeriodStats;
  top_queries: TopQuery[];
}
