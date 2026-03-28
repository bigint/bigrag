package bigrag

import (
	"errors"
	"fmt"
)

// Error represents an API error returned by bigRAG.
type Error struct {
	// StatusCode is the HTTP status code.
	StatusCode int `json:"status_code"`
	// Code is the machine-readable error code (e.g. "NAMESPACE_NOT_FOUND").
	Code string `json:"code,omitempty"`
	// Message is the human-readable error description.
	Message string `json:"message"`
}

// Error implements the error interface.
func (e *Error) Error() string {
	if e.Code != "" {
		return fmt.Sprintf("bigrag: %d %s: %s", e.StatusCode, e.Code, e.Message)
	}
	return fmt.Sprintf("bigrag: %d: %s", e.StatusCode, e.Message)
}

// IsBadRequest reports whether err is a 400 Bad Request error.
func IsBadRequest(err error) bool {
	return hasStatus(err, 400)
}

// IsNotFound reports whether err is a 404 Not Found error.
func IsNotFound(err error) bool {
	return hasStatus(err, 404)
}

// IsRateLimited reports whether err is a 429 Too Many Requests error.
func IsRateLimited(err error) bool {
	return hasStatus(err, 429)
}

// IsAuthError reports whether err is a 401 Unauthorized error.
func IsAuthError(err error) bool {
	return hasStatus(err, 401)
}

// IsConflict reports whether err is a 409 Conflict error.
func IsConflict(err error) bool {
	return hasStatus(err, 409)
}

// IsServerError reports whether err is a 5xx server error.
func IsServerError(err error) bool {
	var apiErr *Error
	if errors.As(err, &apiErr) {
		return apiErr.StatusCode >= 500 && apiErr.StatusCode < 600
	}
	return false
}

// hasStatus checks whether err is an *Error with the given HTTP status code.
func hasStatus(err error, code int) bool {
	var apiErr *Error
	if errors.As(err, &apiErr) {
		return apiErr.StatusCode == code
	}
	return false
}
