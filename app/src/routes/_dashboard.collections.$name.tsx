import { Badge, Page } from "@atelier/ui";
import { createFileRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import { ArrowLeft, Layers, type Settings } from "lucide-react";
import { LinkTabs } from "@/components/navigation/link-tabs";
import { decodeCollectionName } from "@/features/collections/use-collection-name";
import { useCollection, useCollectionStats } from "@/hooks/use-collections";
import { formatBytes, formatNumber } from "@/lib/format";

export const Route = createFileRoute("/_dashboard/collections/$name")({
  component: () => <CollectionLayout />,
});

const CollectionLayout = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeCollectionName(rawName);
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const { data: collection } = useCollection(name);
  const { data: stats } = useCollectionStats(name);

  const base = `/collections/${encodeURIComponent(name)}`;
  const tabs = [
    { href: base, label: "Overview", exact: true },
    { href: `${base}/documents`, label: "Documents", count: stats?.document_count },
    { href: `${base}/connectors`, label: "Connectors" },
    { href: `${base}/search`, label: "Search" },
    { href: `${base}/settings`, label: "Settings" },
  ].map((t) => ({
    ...t,
    active: t.exact
      ? pathname === t.href
      : pathname === t.href || pathname.startsWith(`${t.href}/`),
  }));

  return (
    <Page.Shell>
      <Link
        to="/collections"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        All collections
      </Link>

      <Page.Header
        className="mb-0"
        eyebrow="Collection"
        title={name}
        description={collection?.description || "No description set."}
        actions={
          collection && (
            <div className="hidden items-center gap-2 md:flex">
              <Badge variant="primary">Model {collection.embedding_model}</Badge>
              <Badge variant="neutral">
                Storage{" "}
                {collection.vector_store_provider === "turbopuffer" ? "Turbopuffer" : "Qdrant"}
              </Badge>
              <Badge variant="neutral">Dimensions {collection.dimension}d</Badge>
              {collection.reranking_enabled && (
                <Badge variant="info">rerank: {collection.reranking_model}</Badge>
              )}
            </div>
          )
        }
      />

      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Documents" value={formatNumber(stats.document_count)} />
          <Stat label="Chunks" value={formatNumber(stats.total_chunks)} icon={Layers} />
          <Stat label="Tokens" value={formatNumber(stats.total_tokens)} />
          <Stat label="Storage" value={formatBytes(stats.total_size_bytes)} />
        </div>
      )}

      <LinkTabs tabs={tabs} />

      <div>
        <Outlet />
      </div>
    </Page.Shell>
  );
};

const Stat = ({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon?: typeof Settings;
}) => (
  <div className="rounded-xl border border-border bg-card p-4">
    <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground">
      <span>{label}</span>
      {Icon && <Icon className="h-3.5 w-3.5" />}
    </div>
    <div className="mt-2 text-2xl font-semibold tabular-nums tracking-normal">{value}</div>
  </div>
);
