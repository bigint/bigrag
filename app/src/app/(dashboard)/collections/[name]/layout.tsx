"use client";

import { ArrowLeft, Layers, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { use } from "react";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { LinkTabs } from "@/components/ui/tabs";
import { useCollection, useCollectionStats } from "@/hooks/use-collections";
import { formatBytes, formatNumber } from "@/lib/format";

const CollectionLayout = ({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ name: string }>;
}) => {
  const { name: rawName } = use(params);
  const name = decodeURIComponent(rawName);
  const pathname = usePathname();
  const { data: collection } = useCollection(name);
  const { data: stats } = useCollectionStats(name);

  const base = `/collections/${encodeURIComponent(name)}`;
  const tabs = [
    { href: `${base}/documents`, label: "Documents", count: stats?.document_count },
    { href: `${base}/search`, label: "Search" },
    { href: `${base}/settings`, label: "Settings" },
  ].map((t) => ({ ...t, active: pathname === t.href || pathname.startsWith(`${t.href}/`) }));

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/collections"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        All collections
      </Link>

      <PageHeader
        eyebrow="Collection"
        title={name}
        description={collection?.description || "No description set."}
        actions={
          collection && (
            <div className="hidden items-center gap-2 md:flex">
              <Badge variant="accent">{collection.embedding_model}</Badge>
              <Badge variant="neutral">{collection.dimension}d</Badge>
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

      <div>{children}</div>
    </div>
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
  <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
    <div className="flex items-center justify-between text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
      <span>{label}</span>
      {Icon && <Icon className="h-3.5 w-3.5" />}
    </div>
    <div className="mt-1 text-xl font-semibold tabular-nums tracking-tight">{value}</div>
  </div>
);

export default CollectionLayout;
