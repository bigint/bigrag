import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowUpRight, BookOpen, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Page } from "@/components/ui/page";
import { Tooltip } from "@/components/ui/tooltip";
import { CreateCollectionModal } from "@/features/collections/create-collection-modal";
import { useCollections } from "@/hooks/use-collections";
import { formatNumber, formatRelative } from "@/lib/format";
import type { Collection } from "@/types/bigrag";

type CollectionsSearch = {
  create?: boolean;
};

export const Route = createFileRoute("/_dashboard/collections/")({
  validateSearch: (search: Record<string, unknown>): CollectionsSearch =>
    search.create === "1" || search.create === true ? { create: true } : {},
  component: () => <CollectionsPage />,
});

const CollectionsPage = () => {
  const navigate = useNavigate();
  const { create } = Route.useSearch();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const { data, error, isPending, refetch } = useCollections();
  const modalOpen = open || Boolean(create);
  const closeModal = () => {
    setOpen(false);
    if (create) navigate({ to: "/collections", search: () => ({}), replace: true });
  };

  const items = useMemo(() => {
    if (!data) return [];
    const needle = q.trim().toLowerCase();
    if (!needle) return data.collections;
    return data.collections.filter(
      (c) => c.name.toLowerCase().includes(needle) || c.description.toLowerCase().includes(needle),
    );
  }, [data, q]);

  const columns: Column<Collection>[] = [
    {
      header: "Name",
      key: "name",
      render: (c) => (
        <Link
          className="text-sm font-medium hover:text-muted-foreground"
          params={{ name: c.name }}
          to="/collections/$name"
        >
          {c.name}
        </Link>
      ),
    },
    {
      header: "Model",
      key: "model",
      className: "font-mono text-xs text-muted-foreground",
      render: (c) => c.embedding_model,
    },
    {
      header: "Dim",
      key: "dimension",
      className: "tabular-nums text-muted-foreground",
      render: (c) => c.dimension,
    },
    {
      header: "Docs",
      key: "documents",
      className: "tabular-nums text-muted-foreground",
      render: (c) => formatNumber(c.document_count),
    },
    {
      header: "Mode",
      key: "mode",
      render: (c) => <Badge variant="neutral">{c.default_search_mode}</Badge>,
    },
    {
      header: "Updated",
      key: "updated_at",
      className: "text-muted-foreground",
      render: (c) => formatRelative(c.updated_at),
    },
    {
      header: "Open",
      headerClassName: "text-right",
      className: "text-right",
      key: "actions",
      render: (c) => (
        <div className="flex items-center justify-end">
          <Tooltip content="Open collection">
            <Link
              aria-label={`Open ${c.name}`}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              params={{ name: c.name }}
              to="/collections/$name"
            >
              <ArrowUpRight className="size-4" />
            </Link>
          </Tooltip>
        </div>
      ),
    },
  ];

  return (
    <Page.Shell>
      <Page.Header
        className="mb-0"
        title="Collections"
        description="Group documents, chunks, and vectors under one embedding config."
        actions={
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row-reverse sm:items-center">
            <Button onClick={() => setOpen(true)}>
              <Plus className="h-4 w-4" />
              New collection
            </Button>
            <div className="relative w-full sm:w-72 lg:w-80">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute top-1/2 left-3 z-10 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                aria-label="Search collections"
                className="h-9 border-border bg-muted/70 pr-3 pl-9 shadow-sm shadow-soft-shadow placeholder:text-muted-foreground/75 focus-visible:bg-background"
                placeholder="Search collections"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
          </div>
        }
      />

      <DataTable
        columns={columns}
        data={items}
        emptyAction={
          !q && (
            <Button onClick={() => setOpen(true)} size="sm">
              <Plus className="size-4" /> New collection
            </Button>
          )
        }
        emptyDescription={
          q
            ? "Try a different search term."
            : "Create a collection to start indexing documents for retrieval."
        }
        emptyIcon={<BookOpen className="size-6" />}
        emptyTitle={q ? "No collections match" : "No collections yet"}
        error={error}
        errorAction={
          <Button onClick={() => refetch()} size="sm" variant="secondary">
            Retry
          </Button>
        }
        errorTitle="Couldn't load collections"
        keyExtractor={(c) => c.id}
        loading={isPending}
        loadingMessage="Loading collections..."
      />

      <CreateCollectionModal open={modalOpen} onClose={closeModal} />
    </Page.Shell>
  );
};
