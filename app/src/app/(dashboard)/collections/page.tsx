"use client";

import { BookOpen, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { useCollections } from "@/hooks/use-collections";
import { formatNumber, formatRelative } from "@/lib/format";
import { CreateCollectionModal } from "./components/create-collection-modal";

const CollectionsPage = () => {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const { data, isPending } = useCollections();

  const items = useMemo(() => {
    if (!data) return [];
    const needle = q.trim().toLowerCase();
    if (!needle) return data.collections;
    return data.collections.filter(
      (c) => c.name.toLowerCase().includes(needle) || c.description.toLowerCase().includes(needle),
    );
  }, [data, q]);

  return (
    <div className="flex w-full flex-col gap-6">
      <PageHeader
        title="Collections"
        description="A collection groups documents, chunks and vectors with a shared embedding config."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" />
            New collection
          </Button>
        }
      />

      <div className="max-w-md">
        <Input
          placeholder="Search collections..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          trailing={<Search className="h-4 w-4" />}
        />
      </div>

      {isPending ? (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      ) : items.length === 0 ? (
        <Empty
          icon={<BookOpen className="size-6" />}
          title={q ? "No collections match" : "No collections yet"}
          description={
            q
              ? "Try a different search term."
              : "Create a collection to start indexing documents for retrieval."
          }
          action={
            !q && (
              <Button onClick={() => setOpen(true)} size="sm">
                <Plus className="size-4" /> New collection
              </Button>
            )
          }
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {items.map((c) => (
            <Link
              key={c.id}
              href={`/collections/${encodeURIComponent(c.name)}`}
              className="group overflow-hidden rounded-3xl border border-border bg-card transition-all duration-200 ease-out hover:border-neutral-200 active:scale-95"
            >
              <div className="flex min-h-16 items-start justify-between gap-3 px-5 pt-5 pb-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold tracking-normal">{c.name}</div>
                  <div className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                    {c.description || "—"}
                  </div>
                </div>
                <Badge variant="primary">{c.embedding_provider}</Badge>
              </div>
              <div className="flex items-center justify-between bg-muted px-5 py-3 text-xs">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <span className="font-semibold text-foreground">
                    {formatNumber(c.document_count)} docs
                  </span>
                  <span className="opacity-40">·</span>
                  <span>{c.dimension}d</span>
                </div>
                <span className="text-muted-foreground">{formatRelative(c.updated_at)}</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      <CreateCollectionModal open={open} onClose={() => setOpen(false)} />
    </div>
  );
};

export default CollectionsPage;
