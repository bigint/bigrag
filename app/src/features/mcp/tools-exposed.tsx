const TOOLS_UNSCOPED = [
  { name: "list_collections", description: "Discover which collections this key can read." },
  { name: "get_collection", description: "Embedding/chunking config for one collection." },
  { name: "get_collection_stats", description: "Document/chunk/token counts for one collection." },
  { name: "query", description: "Top-k chunks from a collection. Semantic, keyword, or hybrid." },
  {
    name: "multi_collection_query",
    description: "Search several collections in parallel when the target is unknown.",
  },
  { name: "list_documents", description: "Paginate a collection's documents." },
  { name: "get_document", description: "One document's metadata." },
  { name: "get_document_chunks", description: "Every chunk of a document in order." },
] as const;

const TOOLS_SCOPED = [
  { name: "get_collection", description: "Pinned collection's metadata." },
  { name: "get_collection_stats", description: "Pinned collection's counts." },
  { name: "query", description: "Top-k chunks (collection pre-bound)." },
  { name: "list_documents", description: "Pinned collection's documents." },
  { name: "get_document", description: "One document's metadata (pinned collection)." },
  { name: "get_document_chunks", description: "Every chunk of a document (pinned collection)." },
] as const;

export const ToolsExposed = ({ isScoped }: { isScoped: boolean }) => (
  <section>
    <h3 className="mb-2 font-medium text-sm">
      Tools exposed {isScoped ? "(scoped set)" : "(full set)"}
    </h3>
    <ul className="divide-y divide-border">
      {(isScoped ? TOOLS_SCOPED : TOOLS_UNSCOPED).map((tool) => (
        <li className="flex items-start gap-3 py-2 first:pt-0 last:pb-0" key={tool.name}>
          <code className="mt-0.5 shrink-0 font-mono text-sm">{tool.name}</code>
          <span className="text-sm text-muted-foreground">{tool.description}</span>
        </li>
      ))}
    </ul>
  </section>
);
