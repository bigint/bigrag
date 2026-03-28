package bigrag

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
)

// Namespace provides operations on a single bigRAG namespace.
type Namespace struct {
	client *Client
	// Name is the namespace identifier.
	Name string
}

// Upsert inserts or replaces rows in the namespace.
//
// Each UpsertRow must have an ID. Vectors and attributes are optional.
// If a row with the same ID already exists, it is fully replaced.
func (ns *Namespace) Upsert(ctx context.Context, rows []UpsertRow, opts *UpsertOptions) (*WriteResponse, error) {
	body := make(map[string]interface{})
	body["upsert_rows"] = rows

	if opts != nil {
		if opts.DistanceMetric != "" {
			body["distance_metric"] = opts.DistanceMetric
		}
		if opts.Schema != nil {
			body["schema"] = opts.Schema
		}
		if opts.Condition != nil {
			body["upsert_condition"] = opts.Condition
		}
	}

	headers := map[string]string{}
	if opts != nil && opts.DisableBackpressure {
		headers["X-BigRAG-Disable-Backpressure"] = "true"
	}

	var resp WriteResponse
	path := fmt.Sprintf("/v2/namespaces/%s", url.PathEscape(ns.Name))
	if err := ns.client.doRequestWithHeaders(ctx, http.MethodPost, path, body, headers, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// Query executes a query against the namespace.
//
// Use QueryOptions to configure ranking, filtering, pagination, and other parameters.
func (ns *Namespace) Query(ctx context.Context, opts *QueryOptions) (*QueryResponse, error) {
	if opts == nil {
		opts = &QueryOptions{}
	}

	body := make(map[string]interface{})

	// Single query mode.
	if opts.RankBy != nil {
		body["rank_by"] = opts.RankBy
	}
	if opts.TopK > 0 {
		body["top_k"] = opts.TopK
	}
	if opts.Filters != nil {
		body["filters"] = opts.Filters
	}
	if opts.IncludeAttributes != nil {
		body["include_attributes"] = opts.IncludeAttributes
	}
	if opts.IncludeVectors != nil {
		body["include_vectors"] = *opts.IncludeVectors
	}
	if opts.DistanceCutoff != nil {
		body["distance_cutoff"] = *opts.DistanceCutoff
	}
	if opts.RecallTarget != nil {
		body["recall_target"] = *opts.RecallTarget
	}
	if opts.Cursor != "" {
		body["cursor"] = opts.Cursor
	}
	if opts.Consistency != "" {
		body["consistency"] = opts.Consistency
	}

	// Multi-query mode.
	if len(opts.Queries) > 0 {
		body["queries"] = opts.Queries
	}
	if opts.Fusion != nil {
		body["fusion"] = opts.Fusion
	}
	if len(opts.Aggregations) > 0 {
		body["aggregations"] = opts.Aggregations
	}

	var resp QueryResponse
	path := fmt.Sprintf("/v2/namespaces/%s/query", url.PathEscape(ns.Name))
	if err := ns.client.doRequest(ctx, http.MethodPost, path, body, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// Delete removes rows by their IDs.
//
// IDs can be strings, integers, or UUIDs matching the namespace's ID type.
func (ns *Namespace) Delete(ctx context.Context, ids []interface{}) (*WriteResponse, error) {
	body := map[string]interface{}{
		"deletes": ids,
	}

	var resp WriteResponse
	path := fmt.Sprintf("/v2/namespaces/%s", url.PathEscape(ns.Name))
	if err := ns.client.doRequest(ctx, http.MethodPost, path, body, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// DeleteAll deletes the entire namespace and all its data. This is irreversible.
func (ns *Namespace) DeleteAll(ctx context.Context) error {
	path := fmt.Sprintf("/v2/namespaces/%s", url.PathEscape(ns.Name))
	return ns.client.doRequest(ctx, http.MethodDelete, path, nil, nil)
}

// DeleteByFilter deletes all rows matching the given filter expression.
//
// The filter uses the bigRAG filter DSL. At most 5,000,000 rows can be deleted per call.
func (ns *Namespace) DeleteByFilter(ctx context.Context, filter interface{}, opts *DeleteByFilterOptions) (*WriteResponse, error) {
	body := map[string]interface{}{
		"delete_by_filter": filter,
	}
	if opts != nil {
		if opts.MaxAffected > 0 {
			body["delete_by_filter_max_affected"] = opts.MaxAffected
		}
		if opts.AllowPartial {
			body["delete_by_filter_allow_partial"] = true
		}
	}

	var resp WriteResponse
	path := fmt.Sprintf("/v2/namespaces/%s", url.PathEscape(ns.Name))
	if err := ns.client.doRequest(ctx, http.MethodPost, path, body, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// Patch performs partial updates on rows.
//
// Only the specified attributes are updated; unspecified attributes are preserved.
// Vectors are NOT changed unless explicitly included.
func (ns *Namespace) Patch(ctx context.Context, rows []PatchRow) (*WriteResponse, error) {
	body := map[string]interface{}{
		"patch_rows": rows,
	}

	var resp WriteResponse
	path := fmt.Sprintf("/v2/namespaces/%s", url.PathEscape(ns.Name))
	if err := ns.client.doRequest(ctx, http.MethodPost, path, body, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// Metadata returns metadata about the namespace including schema, document count,
// index state, and storage information.
func (ns *Namespace) Metadata(ctx context.Context) (*NamespaceMetadata, error) {
	var resp NamespaceMetadata
	path := fmt.Sprintf("/v1/namespaces/%s/metadata", url.PathEscape(ns.Name))
	if err := ns.client.doRequest(ctx, http.MethodGet, path, nil, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// Schema returns the current schema for the namespace.
func (ns *Namespace) Schema(ctx context.Context) (map[string]interface{}, error) {
	var resp map[string]interface{}
	path := fmt.Sprintf("/v1/namespaces/%s/schema", url.PathEscape(ns.Name))
	if err := ns.client.doRequest(ctx, http.MethodGet, path, nil, &resp); err != nil {
		return nil, err
	}
	return resp, nil
}

// UpdateSchema updates the schema for the namespace.
//
// Some schema changes trigger background index rebuilds. See the bigRAG documentation
// for details on online schema updates.
func (ns *Namespace) UpdateSchema(ctx context.Context, schema map[string]interface{}) error {
	path := fmt.Sprintf("/v1/namespaces/%s/schema", url.PathEscape(ns.Name))
	return ns.client.doRequest(ctx, http.MethodPut, path, schema, nil)
}

// Recall evaluates the approximate nearest neighbor recall quality of the namespace's index.
//
// This runs random queries and compares ANN results against exact kNN results.
func (ns *Namespace) Recall(ctx context.Context, opts *RecallOptions) (*RecallResult, error) {
	params := url.Values{}
	if opts != nil {
		if opts.NumQueries > 0 {
			params.Set("num", strconv.Itoa(opts.NumQueries))
		}
		if opts.TopK > 0 {
			params.Set("top_k", strconv.Itoa(opts.TopK))
		}
	}

	path := fmt.Sprintf("/v1/namespaces/%s/_debug/recall", url.PathEscape(ns.Name))
	if len(params) > 0 {
		path += "?" + params.Encode()
	}

	var resp RecallResult
	if err := ns.client.doRequest(ctx, http.MethodPost, path, nil, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}
