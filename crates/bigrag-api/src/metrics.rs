use metrics::{counter, describe_counter, describe_gauge, describe_histogram, gauge, histogram};

/// Register all metric descriptions (call once at startup).
pub fn register_metrics() {
    describe_counter!("bigrag_queries_total", "Total query requests");
    describe_counter!("bigrag_writes_total", "Total write requests");
    describe_counter!("bigrag_deletes_total", "Total delete requests");
    describe_histogram!("bigrag_query_duration_seconds", "Query latency in seconds");
    describe_histogram!("bigrag_write_duration_seconds", "Write latency in seconds");
    describe_gauge!("bigrag_namespace_count", "Number of active namespaces");
    describe_counter!("bigrag_errors_total", "Total error responses");
    describe_gauge!("bigrag_info", "Server info");
    describe_counter!("bigrag_requests_total", "Total HTTP requests");
    describe_histogram!(
        "bigrag_request_duration_seconds",
        "HTTP request duration in seconds"
    );
}

/// Record a query operation.
pub fn record_query(namespace: &str, duration: std::time::Duration, success: bool) {
    counter!(
        "bigrag_queries_total",
        "namespace" => namespace.to_string(),
        "status" => if success { "ok" } else { "error" }
    )
    .increment(1);
    histogram!(
        "bigrag_query_duration_seconds",
        "namespace" => namespace.to_string()
    )
    .record(duration.as_secs_f64());
}

/// Record a write operation.
pub fn record_write(namespace: &str, duration: std::time::Duration, rows: usize) {
    counter!(
        "bigrag_writes_total",
        "namespace" => namespace.to_string(),
        "rows" => rows.to_string()
    )
    .increment(1);
    histogram!(
        "bigrag_write_duration_seconds",
        "namespace" => namespace.to_string()
    )
    .record(duration.as_secs_f64());
}

/// Record a delete operation.
pub fn record_delete(namespace: &str, count: usize) {
    counter!(
        "bigrag_deletes_total",
        "namespace" => namespace.to_string(),
        "count" => count.to_string()
    )
    .increment(1);
}

/// Record an error by HTTP status code.
pub fn record_error(status: u16) {
    counter!("bigrag_errors_total", "status" => status.to_string()).increment(1);
}

/// Update the active namespace count gauge.
pub fn set_namespace_count(count: usize) {
    gauge!("bigrag_namespace_count").set(count as f64);
}
