export interface AccessLogEntry {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  api_key_id: string | null;
  api_key_name: string | null;
  auth_method: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  collection_name: string | null;
  method: string;
  path: string;
  route: string | null;
  status_code: number;
  success: boolean;
  latency_ms: number;
  request_id: string | null;
  metadata: Record<string, unknown>;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AccessLogListResponse {
  entries: AccessLogEntry[];
  total: number;
}

export interface AccessLogBucket {
  label: string;
  count: number;
  avg_latency_ms: number | null;
}

export interface AccessLogTimelinePoint {
  bucket: string;
  events: number;
  errors: number;
  avg_latency_ms: number;
}

export interface AccessLogOverviewResponse {
  window_days: number;
  total_events: number;
  success_rate: number;
  error_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  unique_users: number;
  query_events: number;
  by_action: AccessLogBucket[];
  latency_by_action: AccessLogBucket[];
  timeline: AccessLogTimelinePoint[];
  recent: AccessLogEntry[];
}
