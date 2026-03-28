// Package bigrag provides a Go client for the bigRAG vector and full-text search database.
//
// Create a client with functional options:
//
//	client := bigrag.NewClient(
//	    bigrag.WithAPIKey("your-api-key"),
//	    bigrag.WithBaseURL("http://localhost:8080"),
//	)
//
// Work with namespaces:
//
//	ns := client.Namespace("my-namespace")
//	resp, err := ns.Upsert(ctx, rows, nil)
//	results, err := ns.Query(ctx, &bigrag.QueryOptions{...})
package bigrag

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const (
	defaultBaseURL    = "http://localhost:8080"
	defaultTimeout    = 30 * time.Second
	defaultMaxRetries = 2
)

// Client is the bigRAG API client.
type Client struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
	maxRetries int
}

// ClientOption configures a Client.
type ClientOption func(*Client)

// NewClient creates a new bigRAG client with the given options.
//
// If no base URL is specified, it defaults to http://localhost:8080.
// If no timeout is specified, it defaults to 30 seconds.
// If no max retries is specified, it defaults to 2.
func NewClient(opts ...ClientOption) *Client {
	c := &Client{
		baseURL:    defaultBaseURL,
		httpClient: &http.Client{Timeout: defaultTimeout},
		maxRetries: defaultMaxRetries,
	}
	for _, opt := range opts {
		opt(c)
	}
	// Normalize trailing slash.
	c.baseURL = strings.TrimRight(c.baseURL, "/")
	return c
}

// WithAPIKey sets the API key used for authentication.
func WithAPIKey(key string) ClientOption {
	return func(c *Client) {
		c.apiKey = key
	}
}

// WithBaseURL sets the base URL for the bigRAG API.
func WithBaseURL(rawURL string) ClientOption {
	return func(c *Client) {
		c.baseURL = rawURL
	}
}

// WithTimeout sets the HTTP request timeout.
func WithTimeout(d time.Duration) ClientOption {
	return func(c *Client) {
		c.httpClient.Timeout = d
	}
}

// WithMaxRetries sets the maximum number of retries for failed requests.
// Retries use exponential backoff and only apply to 429 and 5xx responses.
func WithMaxRetries(n int) ClientOption {
	return func(c *Client) {
		c.maxRetries = n
	}
}

// WithHTTPClient sets a custom http.Client for requests.
func WithHTTPClient(hc *http.Client) ClientOption {
	return func(c *Client) {
		c.httpClient = hc
	}
}

// Namespace returns a Namespace handle for the given name.
// No network request is made until a method is called on the returned handle.
func (c *Client) Namespace(name string) *Namespace {
	return &Namespace{client: c, Name: name}
}

// Namespaces lists all namespaces, with optional filtering and pagination.
func (c *Client) Namespaces(ctx context.Context, opts *NamespaceListOptions) (*NamespaceListResponse, error) {
	params := url.Values{}
	if opts != nil {
		if opts.Prefix != "" {
			params.Set("prefix", opts.Prefix)
		}
		if opts.Cursor != "" {
			params.Set("cursor", opts.Cursor)
		}
		if opts.PageSize > 0 {
			params.Set("page_size", strconv.Itoa(opts.PageSize))
		}
	}

	path := "/v1/namespaces"
	if len(params) > 0 {
		path += "?" + params.Encode()
	}

	var resp NamespaceListResponse
	if err := c.doRequest(ctx, http.MethodGet, path, nil, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// Health checks the health of the bigRAG server.
func (c *Client) Health(ctx context.Context) (*HealthResponse, error) {
	var resp HealthResponse
	if err := c.doRequest(ctx, http.MethodGet, "/health", nil, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// doRequest executes an HTTP request with retries and error handling.
func (c *Client) doRequest(ctx context.Context, method, path string, body interface{}, result interface{}) error {
	var bodyReader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("bigrag: failed to marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(data)
	}

	var lastErr error
	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			// Exponential backoff: 100ms, 200ms, 400ms, ...
			backoff := time.Duration(1<<uint(attempt-1)) * 100 * time.Millisecond
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(backoff):
			}
			// Reset the reader for retry.
			if body != nil {
				data, _ := json.Marshal(body)
				bodyReader = bytes.NewReader(data)
			}
		}

		req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, bodyReader)
		if err != nil {
			return fmt.Errorf("bigrag: failed to create request: %w", err)
		}
		if body != nil {
			req.Header.Set("Content-Type", "application/json")
		}
		if c.apiKey != "" {
			req.Header.Set("Authorization", "Bearer "+c.apiKey)
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("bigrag: request failed: %w", err)
			continue
		}

		respBody, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			lastErr = fmt.Errorf("bigrag: failed to read response body: %w", err)
			continue
		}

		// Success.
		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			if result != nil && len(respBody) > 0 {
				if err := json.Unmarshal(respBody, result); err != nil {
					return fmt.Errorf("bigrag: failed to decode response: %w", err)
				}
			}
			return nil
		}

		// Parse error response.
		apiErr := parseErrorResponse(resp.StatusCode, respBody)

		// Only retry on 429 (rate limited) and 5xx (server errors).
		if resp.StatusCode == 429 || resp.StatusCode >= 500 {
			lastErr = apiErr
			continue
		}

		// Non-retryable error.
		return apiErr
	}

	return lastErr
}

// doRequestWithHeaders is like doRequest but allows setting extra headers.
func (c *Client) doRequestWithHeaders(ctx context.Context, method, path string, body interface{}, headers map[string]string, result interface{}) error {
	var bodyReader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("bigrag: failed to marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(data)
	}

	var lastErr error
	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(1<<uint(attempt-1)) * 100 * time.Millisecond
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(backoff):
			}
			if body != nil {
				data, _ := json.Marshal(body)
				bodyReader = bytes.NewReader(data)
			}
		}

		req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, bodyReader)
		if err != nil {
			return fmt.Errorf("bigrag: failed to create request: %w", err)
		}
		if body != nil {
			req.Header.Set("Content-Type", "application/json")
		}
		if c.apiKey != "" {
			req.Header.Set("Authorization", "Bearer "+c.apiKey)
		}
		for k, v := range headers {
			req.Header.Set(k, v)
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("bigrag: request failed: %w", err)
			continue
		}

		respBody, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			lastErr = fmt.Errorf("bigrag: failed to read response body: %w", err)
			continue
		}

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			if result != nil && len(respBody) > 0 {
				if err := json.Unmarshal(respBody, result); err != nil {
					return fmt.Errorf("bigrag: failed to decode response: %w", err)
				}
			}
			return nil
		}

		apiErr := parseErrorResponse(resp.StatusCode, respBody)

		if resp.StatusCode == 429 || resp.StatusCode >= 500 {
			lastErr = apiErr
			continue
		}

		return apiErr
	}

	return lastErr
}

// parseErrorResponse parses an error response body into an *Error.
func parseErrorResponse(statusCode int, body []byte) *Error {
	// Try to parse structured error response.
	var errResp struct {
		Error struct {
			Code    string `json:"code"`
			Message string `json:"message"`
		} `json:"error"`
		// Fallback: top-level message field.
		Message string `json:"message"`
		Code    string `json:"code"`
	}

	apiErr := &Error{StatusCode: statusCode}

	if err := json.Unmarshal(body, &errResp); err == nil {
		if errResp.Error.Message != "" {
			apiErr.Code = errResp.Error.Code
			apiErr.Message = errResp.Error.Message
		} else if errResp.Message != "" {
			apiErr.Code = errResp.Code
			apiErr.Message = errResp.Message
		} else {
			apiErr.Message = string(body)
		}
	} else {
		apiErr.Message = string(body)
	}

	if apiErr.Message == "" {
		apiErr.Message = http.StatusText(statusCode)
	}

	return apiErr
}
