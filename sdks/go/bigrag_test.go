package bigrag

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestNewClientDefaults(t *testing.T) {
	c := NewClient()
	if c.baseURL != defaultBaseURL {
		t.Errorf("expected base URL %q, got %q", defaultBaseURL, c.baseURL)
	}
	if c.apiKey != "" {
		t.Errorf("expected empty API key, got %q", c.apiKey)
	}
	if c.maxRetries != defaultMaxRetries {
		t.Errorf("expected max retries %d, got %d", defaultMaxRetries, c.maxRetries)
	}
}

func TestNewClientWithOptions(t *testing.T) {
	c := NewClient(
		WithAPIKey("test-key"),
		WithBaseURL("http://example.com/"),
		WithMaxRetries(5),
		WithTimeout(60*time.Second),
	)
	if c.apiKey != "test-key" {
		t.Errorf("expected API key %q, got %q", "test-key", c.apiKey)
	}
	// Trailing slash should be trimmed.
	if c.baseURL != "http://example.com" {
		t.Errorf("expected base URL %q, got %q", "http://example.com", c.baseURL)
	}
	if c.maxRetries != 5 {
		t.Errorf("expected max retries 5, got %d", c.maxRetries)
	}
}

func TestNamespaceHandle(t *testing.T) {
	c := NewClient()
	ns := c.Namespace("test-ns")
	if ns.Name != "test-ns" {
		t.Errorf("expected namespace name %q, got %q", "test-ns", ns.Name)
	}
	if ns.client != c {
		t.Error("expected namespace client to reference the parent client")
	}
}

func TestHealth(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/health" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		if r.Method != http.MethodGet {
			t.Errorf("unexpected method: %s", r.Method)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(HealthResponse{Status: "ok", Version: "1.0.0"})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	resp, err := c.Health(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Status != "ok" {
		t.Errorf("expected status %q, got %q", "ok", resp.Status)
	}
	if resp.Version != "1.0.0" {
		t.Errorf("expected version %q, got %q", "1.0.0", resp.Version)
	}
}

func TestNamespaces(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/namespaces" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		if r.URL.Query().Get("prefix") != "test-" {
			t.Errorf("expected prefix query param %q, got %q", "test-", r.URL.Query().Get("prefix"))
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(NamespaceListResponse{
			Namespaces: []NamespaceSummary{
				{ID: "test-ns1", DocCount: 100},
				{ID: "test-ns2", DocCount: 200},
			},
			NextCursor: "abc",
		})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	resp, err := c.Namespaces(context.Background(), &NamespaceListOptions{Prefix: "test-"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(resp.Namespaces) != 2 {
		t.Fatalf("expected 2 namespaces, got %d", len(resp.Namespaces))
	}
	if resp.Namespaces[0].ID != "test-ns1" {
		t.Errorf("expected first namespace ID %q, got %q", "test-ns1", resp.Namespaces[0].ID)
	}
	if resp.NextCursor != "abc" {
		t.Errorf("expected next cursor %q, got %q", "abc", resp.NextCursor)
	}
}

func TestAuthHeader(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		auth := r.Header.Get("Authorization")
		if auth != "Bearer my-secret-key" {
			t.Errorf("expected Authorization header %q, got %q", "Bearer my-secret-key", auth)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(HealthResponse{Status: "ok"})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL), WithAPIKey("my-secret-key"))
	_, err := c.Health(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestUpsert(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v2/namespaces/my-ns" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		if r.Method != http.MethodPost {
			t.Errorf("unexpected method: %s", r.Method)
		}
		if r.Header.Get("Content-Type") != "application/json" {
			t.Errorf("expected Content-Type application/json, got %s", r.Header.Get("Content-Type"))
		}

		var body map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("failed to decode body: %v", err)
		}
		rows, ok := body["upsert_rows"].([]interface{})
		if !ok || len(rows) != 2 {
			t.Fatalf("expected 2 upsert rows, got %v", body["upsert_rows"])
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(WriteResponse{Status: "ok", RowsAffected: 2, RowsUpserted: 2})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	ns := c.Namespace("my-ns")
	resp, err := ns.Upsert(context.Background(), []UpsertRow{
		{ID: "doc-1", Vector: []float64{0.1, 0.2, 0.3}, Attributes: map[string]interface{}{"title": "Doc 1"}},
		{ID: "doc-2", Vector: []float64{0.4, 0.5, 0.6}, Attributes: map[string]interface{}{"title": "Doc 2"}},
	}, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.RowsAffected != 2 {
		t.Errorf("expected 2 rows affected, got %d", resp.RowsAffected)
	}
}

func TestQuery(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v2/namespaces/my-ns/query" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}

		var body map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("failed to decode body: %v", err)
		}
		if body["top_k"] != float64(10) {
			t.Errorf("expected top_k 10, got %v", body["top_k"])
		}

		dist := 0.15
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(QueryResponse{
			Rows: []QueryRow{
				{ID: "doc-1", Dist: &dist, Attributes: map[string]interface{}{"title": "Doc 1"}},
			},
		})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	ns := c.Namespace("my-ns")
	resp, err := ns.Query(context.Background(), &QueryOptions{
		RankBy: []interface{}{"vector", "ANN", []float64{0.1, 0.2, 0.3}},
		TopK:   10,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(resp.Rows) != 1 {
		t.Fatalf("expected 1 row, got %d", len(resp.Rows))
	}
	if resp.Rows[0].ID != "doc-1" {
		t.Errorf("expected row ID %q, got %v", "doc-1", resp.Rows[0].ID)
	}
	if resp.Rows[0].Dist == nil || *resp.Rows[0].Dist != 0.15 {
		t.Errorf("expected dist 0.15, got %v", resp.Rows[0].Dist)
	}
}

func TestDelete(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]interface{}
		json.NewDecoder(r.Body).Decode(&body)
		deletes, ok := body["deletes"].([]interface{})
		if !ok || len(deletes) != 2 {
			t.Fatalf("expected 2 deletes, got %v", body["deletes"])
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(WriteResponse{Status: "ok", RowsAffected: 2, RowsDeleted: 2})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	ns := c.Namespace("my-ns")
	resp, err := ns.Delete(context.Background(), []interface{}{"doc-1", "doc-2"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.RowsDeleted != 2 {
		t.Errorf("expected 2 rows deleted, got %d", resp.RowsDeleted)
	}
}

func TestDeleteAll(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			t.Errorf("expected DELETE, got %s", r.Method)
		}
		if r.URL.Path != "/v2/namespaces/my-ns" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	ns := c.Namespace("my-ns")
	if err := ns.DeleteAll(context.Background()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestPatch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]interface{}
		json.NewDecoder(r.Body).Decode(&body)
		patches, ok := body["patch_rows"].([]interface{})
		if !ok || len(patches) != 1 {
			t.Fatalf("expected 1 patch row, got %v", body["patch_rows"])
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(WriteResponse{Status: "ok", RowsAffected: 1, RowsPatched: 1})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	ns := c.Namespace("my-ns")
	resp, err := ns.Patch(context.Background(), []PatchRow{
		{ID: "doc-1", Attributes: map[string]interface{}{"score": 4.8}},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.RowsPatched != 1 {
		t.Errorf("expected 1 row patched, got %d", resp.RowsPatched)
	}
}

func TestMetadata(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/namespaces/my-ns/metadata" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(NamespaceMetadata{
			ID:             "my-ns",
			ApproxRowCount: 1000,
			DocCount:       1000,
		})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	ns := c.Namespace("my-ns")
	meta, err := ns.Metadata(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if meta.DocCount != 1000 {
		t.Errorf("expected doc count 1000, got %d", meta.DocCount)
	}
}

func TestSchema(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/namespaces/my-ns/schema" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		if r.Method == http.MethodGet {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]interface{}{
				"title": map[string]interface{}{"type": "string", "filterable": true},
			})
		} else if r.Method == http.MethodPut {
			w.WriteHeader(http.StatusOK)
		}
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	ns := c.Namespace("my-ns")

	schema, err := ns.Schema(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if schema["title"] == nil {
		t.Error("expected title in schema")
	}

	err = ns.UpdateSchema(context.Background(), map[string]interface{}{
		"title": map[string]interface{}{"type": "string", "filterable": true, "full_text_search": true},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestErrorParsing(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"error": map[string]interface{}{
				"code":    "NAMESPACE_NOT_FOUND",
				"message": "Namespace 'missing' does not exist",
			},
		})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL), WithMaxRetries(0))
	_, err := c.Namespace("missing").Metadata(context.Background())
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !IsNotFound(err) {
		t.Errorf("expected not found error, got %v", err)
	}

	var apiErr *Error
	if !errors.As(err, &apiErr) {
		t.Fatalf("expected *Error, got %T", err)
	}
	if apiErr.Code != "NAMESPACE_NOT_FOUND" {
		t.Errorf("expected error code %q, got %q", "NAMESPACE_NOT_FOUND", apiErr.Code)
	}
	if apiErr.StatusCode != 404 {
		t.Errorf("expected status 404, got %d", apiErr.StatusCode)
	}
}

func TestErrorHelpers(t *testing.T) {
	tests := []struct {
		name   string
		err    error
		check  func(error) bool
		expect bool
	}{
		{"bad request", &Error{StatusCode: 400}, IsBadRequest, true},
		{"not found", &Error{StatusCode: 404}, IsNotFound, true},
		{"rate limited", &Error{StatusCode: 429}, IsRateLimited, true},
		{"auth error", &Error{StatusCode: 401}, IsAuthError, true},
		{"conflict", &Error{StatusCode: 409}, IsConflict, true},
		{"server error 500", &Error{StatusCode: 500}, IsServerError, true},
		{"server error 503", &Error{StatusCode: 503}, IsServerError, true},
		{"not a server error", &Error{StatusCode: 400}, IsServerError, false},
		{"not an api error", errors.New("network"), IsNotFound, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.check(tt.err); got != tt.expect {
				t.Errorf("expected %v, got %v", tt.expect, got)
			}
		})
	}
}

func TestRetryOn429(t *testing.T) {
	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts < 3 {
			w.Header().Set("Retry-After", "0")
			w.WriteHeader(http.StatusTooManyRequests)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": map[string]interface{}{
					"code":    "RATE_LIMITED",
					"message": "Too many requests",
				},
			})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(HealthResponse{Status: "ok"})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL), WithMaxRetries(3))
	resp, err := c.Health(context.Background())
	if err != nil {
		t.Fatalf("unexpected error after retries: %v", err)
	}
	if resp.Status != "ok" {
		t.Errorf("expected status ok, got %s", resp.Status)
	}
	if attempts != 3 {
		t.Errorf("expected 3 attempts, got %d", attempts)
	}
}

func TestRetryExhausted(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"error": map[string]interface{}{
				"code":    "INTERNAL_ERROR",
				"message": "Something went wrong",
			},
		})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL), WithMaxRetries(1))
	_, err := c.Health(context.Background())
	if err == nil {
		t.Fatal("expected error after exhausted retries")
	}
	if !IsServerError(err) {
		t.Errorf("expected server error, got %v", err)
	}
}

func TestDeleteByFilter(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]interface{}
		json.NewDecoder(r.Body).Decode(&body)
		if body["delete_by_filter"] == nil {
			t.Fatal("expected delete_by_filter in body")
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(WriteResponse{Status: "ok", RowsAffected: 50, RowsDeleted: 50})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	ns := c.Namespace("my-ns")
	resp, err := ns.DeleteByFilter(context.Background(),
		[]interface{}{"status", "Eq", "deprecated"},
		&DeleteByFilterOptions{MaxAffected: 1000},
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.RowsDeleted != 50 {
		t.Errorf("expected 50 rows deleted, got %d", resp.RowsDeleted)
	}
}

func TestUpsertWithOptions(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-BigRAG-Disable-Backpressure") != "true" {
			t.Error("expected X-BigRAG-Disable-Backpressure header")
		}

		var body map[string]interface{}
		json.NewDecoder(r.Body).Decode(&body)
		if body["distance_metric"] != "cosine_distance" {
			t.Errorf("expected distance_metric cosine_distance, got %v", body["distance_metric"])
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(WriteResponse{Status: "ok", RowsAffected: 1})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL))
	ns := c.Namespace("my-ns")
	_, err := ns.Upsert(context.Background(), []UpsertRow{
		{ID: "doc-1", Vector: []float64{0.1, 0.2}},
	}, &UpsertOptions{
		DistanceMetric:      "cosine_distance",
		DisableBackpressure: true,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestContextCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(5 * time.Second)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(HealthResponse{Status: "ok"})
	}))
	defer server.Close()

	c := NewClient(WithBaseURL(server.URL), WithMaxRetries(0), WithTimeout(10*time.Second))
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	_, err := c.Health(ctx)
	if err == nil {
		t.Fatal("expected error from cancelled context")
	}
}

func TestErrorString(t *testing.T) {
	e := &Error{StatusCode: 400, Code: "INVALID_REQUEST", Message: "bad input"}
	expected := "bigrag: 400 INVALID_REQUEST: bad input"
	if e.Error() != expected {
		t.Errorf("expected %q, got %q", expected, e.Error())
	}

	e2 := &Error{StatusCode: 500, Message: "internal error"}
	expected2 := "bigrag: 500: internal error"
	if e2.Error() != expected2 {
		t.Errorf("expected %q, got %q", expected2, e2.Error())
	}
}
