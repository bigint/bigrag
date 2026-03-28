# bigrag-go

Official Go SDK for [bigRAG](https://github.com/bigrag-io/bigrag), a vector and full-text search database.

## Installation

```bash
go get github.com/bigrag-io/bigrag-go
```

## Usage

### Create a client

```go
import bigrag "github.com/bigrag-io/bigrag-go"

client := bigrag.NewClient(
    bigrag.WithAPIKey("your-api-key"),
    bigrag.WithBaseURL("http://localhost:8080"),
)
```

### Upsert documents

```go
ns := client.Namespace("my-namespace")

resp, err := ns.Upsert(ctx, []bigrag.UpsertRow{
    {
        ID:     "doc-1",
        Vector: []float64{0.1, 0.2, 0.3},
        Attributes: map[string]interface{}{
            "title":    "Introduction to RAG",
            "category": "ml",
        },
    },
    {
        ID:     "doc-2",
        Vector: []float64{0.4, 0.5, 0.6},
        Attributes: map[string]interface{}{
            "title":    "Vector Databases",
            "category": "infra",
        },
    },
}, nil)
```

### Query with vector search

```go
results, err := ns.Query(ctx, &bigrag.QueryOptions{
    RankBy: []interface{}{"vector", "ANN", []float64{0.1, 0.2, 0.3}},
    TopK:   10,
    Filters: []interface{}{"category", "Eq", "ml"},
    IncludeAttributes: true,
})

for _, row := range results.Rows {
    fmt.Printf("ID: %v, Dist: %v\n", row.ID, *row.Dist)
}
```

### Full-text search with BM25

```go
results, err := ns.Query(ctx, &bigrag.QueryOptions{
    RankBy: []interface{}{"title", "BM25", "retrieval augmented generation"},
    TopK:   10,
})
```

### Delete documents

```go
// By ID
resp, err := ns.Delete(ctx, []interface{}{"doc-1", "doc-2"})

// By filter
resp, err = ns.DeleteByFilter(ctx,
    []interface{}{"status", "Eq", "deprecated"},
    &bigrag.DeleteByFilterOptions{MaxAffected: 5000},
)

// Entire namespace
err = ns.DeleteAll(ctx)
```

### Patch (partial update)

```go
resp, err := ns.Patch(ctx, []bigrag.PatchRow{
    {
        ID: "doc-1",
        Attributes: map[string]interface{}{
            "score": 4.8,
        },
    },
})
```

### Namespace operations

```go
// List namespaces
list, err := client.Namespaces(ctx, &bigrag.NamespaceListOptions{
    Prefix:   "prod_",
    PageSize: 100,
})

// Get metadata
meta, err := ns.Metadata(ctx)

// Get/update schema
schema, err := ns.Schema(ctx)
err = ns.UpdateSchema(ctx, map[string]interface{}{
    "title": map[string]interface{}{
        "type":             "string",
        "filterable":       true,
        "full_text_search": true,
    },
})
```

### Error handling

```go
_, err := ns.Metadata(ctx)
if bigrag.IsNotFound(err) {
    // Namespace does not exist
} else if bigrag.IsRateLimited(err) {
    // Back off and retry
} else if bigrag.IsAuthError(err) {
    // Invalid API key
}
```

## Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `WithAPIKey(key)` | API key for authentication | none |
| `WithBaseURL(url)` | Base URL of bigRAG server | `http://localhost:8080` |
| `WithTimeout(d)` | HTTP request timeout | 30s |
| `WithMaxRetries(n)` | Max retries for 429/5xx errors | 2 |
| `WithHTTPClient(c)` | Custom `*http.Client` | default |

## License

Apache 2.0
