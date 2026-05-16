import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight, FileText, Search, Settings } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { useCollection, useCollectionStats } from "@/hooks/use-collections";
import { useDocuments } from "@/hooks/use-documents";
import { formatBytes, formatNumber, formatRelative } from "@/lib/format";

export const Route = createFileRoute("/_dashboard/collections/$name/")({
  component: () => <CollectionIndex />,
});

const CollectionIndex = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeURIComponent(rawName);
  const { data: collection, isPending: collectionPending } = useCollection(name);
  const { data: stats } = useCollectionStats(name);
  const { data: documentsData, isPending: documentsPending } = useDocuments(name);
  const recent = documentsData?.documents.slice(0, 5) ?? [];

  if (collectionPending || !collection) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Overview</CardTitle>
          <CardDescription>
            {collection.description || "Collection configuration and recent document activity."}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <Fact label="Embedding model" value={collection.embedding_model} />
          <Fact
            label="Vector storage"
            value={collection.vector_store_provider === "turbopuffer" ? "Turbopuffer" : "Qdrant"}
          />
          <Fact label="Dimensions" value={`${formatNumber(collection.dimension)}d`} />
          <Fact label="Chunking" value={`${collection.chunk_size}/${collection.chunk_overlap}`} />
          <Fact label="Default search" value={collection.default_search_mode} />
          <Fact
            label="API key"
            value={collection.has_api_key ? "Configured" : "Missing"}
            tone={collection.has_api_key ? "success" : "warning"}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Shortcuts</CardTitle>
          <CardDescription>Open the main collection workflows.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2">
          <Shortcut to="/collections/$name/documents" name={name} icon={FileText} label="Documents" />
          <Shortcut to="/collections/$name/search" name={name} icon={Search} label="Search" />
          <Shortcut to="/collections/$name/settings" name={name} icon={Settings} label="Settings" />
        </CardContent>
      </Card>

      <Card className="xl:col-span-2">
        <CardHeader>
          <CardTitle>Status</CardTitle>
          <CardDescription>
            {stats
              ? `${formatNumber(stats.document_count)} documents, ${formatNumber(stats.total_chunks)} chunks, ${formatBytes(stats.total_size_bytes)}`
              : "Loading status..."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {stats && (
            <div className="mb-4 grid gap-2 sm:grid-cols-4">
              {Object.entries(stats.status_counts).map(([status, count]) => (
                <Link
                  key={status}
                  to="/collections/$name/documents"
                  params={{ name }}
                  search={{ status }}
                  className="rounded-md border border-border p-3 hover:bg-muted"
                >
                  <div className="text-xs font-semibold uppercase text-muted-foreground">{status}</div>
                  <div className="mt-1 text-xl font-semibold">{formatNumber(count)}</div>
                </Link>
              ))}
            </div>
          )}
          {documentsPending ? (
            <Spinner />
          ) : recent.length ? (
            <div className="divide-y divide-border rounded-md border border-border">
              {recent.map((document) => (
                <Link
                  key={document.id}
                  to="/collections/$name/documents/$docId"
                  params={{ name, docId: document.id }}
                  className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-muted"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{document.filename}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {formatRelative(document.updated_at)}
                    </div>
                  </div>
                  <Badge variant="neutral">{document.status}</Badge>
                </Link>
              ))}
            </div>
          ) : (
            <Empty title="No documents yet" description="Upload documents from the Documents tab." />
          )}
        </CardContent>
      </Card>
    </div>
  );
};

const Fact = ({
  label,
  tone,
  value,
}: {
  label: string;
  tone?: "success" | "warning";
  value: string;
}) => (
  <div className="rounded-md border border-border bg-background p-3">
    <div className="text-xs text-muted-foreground">{label}</div>
    <div className="mt-1 flex items-center gap-2 text-sm font-semibold">
      {value}
      {tone && <Badge variant={tone}>{tone === "success" ? "ok" : "check"}</Badge>}
    </div>
  </div>
);

const Shortcut = ({
  icon: Icon,
  label,
  name,
  to,
}: {
  icon: typeof FileText;
  label: string;
  name: string;
  to: "/collections/$name/documents" | "/collections/$name/search" | "/collections/$name/settings";
}) => (
  <Link
    to={to}
    params={{ name }}
    className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
  >
    <span className="inline-flex items-center gap-2">
      <Icon className="size-4 text-muted-foreground" />
      {label}
    </span>
    <ArrowUpRight className="size-4 text-muted-foreground" />
  </Link>
);
