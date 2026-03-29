# bigrag-go

Official Go SDK for [bigRAG](https://github.com/bigrag-io/bigrag) — a self-hostable RAG platform.

> **Note**: This SDK is being updated to match the new collections-based API. Some methods may not yet be implemented.

## Installation

```bash
go get github.com/bigrag-io/bigrag-go
```

## Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `WithAPIKey(key)` | API key for authentication | none |
| `WithBaseURL(url)` | Base URL of bigRAG server | `http://localhost:8080` |
| `WithTimeout(d)` | HTTP request timeout | 30s |
| `WithMaxRetries(n)` | Max retries for 429/5xx errors | 2 |

## License

Apache 2.0
