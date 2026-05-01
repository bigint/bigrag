"use client";

import { Check, Copy, ExternalLink, KeyRound, Plug, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Tooltip } from "@/components/ui/tooltip";
import { useCollections } from "@/hooks/use-collections";
import {
  useCreateMcpServer,
  useDeleteMcpServer,
  useMcpServers,
  useRotateMcpServer,
} from "@/hooks/use-mcp-servers";
import { formatRelative } from "@/lib/format";
import type { CreatedMcpServer, McpServer } from "@/types/bigrag";

const UNSCOPED = "__all__";

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

const slugify = (s: string) =>
  s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);

const getOrigin = () => (typeof window !== "undefined" ? window.location.origin : "");

const trimSlash = (s: string) => s.replace(/\/+$/, "");

const buildRemoteUrl = (origin: string, plaintext: string) =>
  `${trimSlash(origin)}/mcp?token=${encodeURIComponent(plaintext)}`;

const buildClaudeDesktopJson = (server: McpServer, origin: string, plaintext: string) =>
  JSON.stringify(
    {
      mcpServers: {
        [server.server_name]: {
          command: "bigrag-mcp",
          env: {
            BIGRAG_URL: trimSlash(origin),
            BIGRAG_API_KEY: plaintext,
          },
        },
      },
    },
    null,
    2,
  );

const shellQuote = (s: string) => `'${s.replace(/'/g, "'\\''")}'`;

const buildShellSnippet = (origin: string, plaintext: string) =>
  `BIGRAG_URL=${shellQuote(trimSlash(origin))} \\
  BIGRAG_API_KEY=${shellQuote(plaintext)} \\
  bigrag-mcp`;

const CopyButton = ({ code, label }: { code: string; label: string }) => {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    toast.success("Copied");
    setTimeout(() => setCopied(false), 1800);
  };
  return (
    <Tooltip content={copied ? "Copied" : "Copy"}>
      <Button
        aria-label={`Copy ${label}`}
        className="h-7 w-7 p-0"
        onClick={copy}
        size="sm"
        variant="secondary"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </Button>
    </Tooltip>
  );
};

const CodeBlock = ({ code, label }: { code: string; label: string }) => (
  <div className="relative">
    <pre className="overflow-x-auto rounded-md border border-border bg-muted/50 p-4 font-mono text-xs leading-relaxed">
      <code>{code}</code>
    </pre>
    <div className="absolute top-2 right-2">
      <CopyButton code={code} label={label} />
    </div>
  </div>
);

interface CreateDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (created: CreatedMcpServer) => void;
  collections: { name: string }[];
}

const CreateDialog = ({ open, onClose, onCreated, collections }: CreateDialogProps) => {
  const create = useCreateMcpServer();
  const [title, setTitle] = useState("");
  const [serverName, setServerName] = useState("");
  const [collection, setCollection] = useState(UNSCOPED);
  const [autoSlug, setAutoSlug] = useState(true);

  useEffect(() => {
    if (!open) {
      setTitle("");
      setServerName("");
      setCollection(UNSCOPED);
      setAutoSlug(true);
    }
  }, [open]);

  useEffect(() => {
    if (autoSlug) setServerName(slugify(title) || "bigrag");
  }, [title, autoSlug]);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!title.trim() || !serverName.trim()) return;
    try {
      const created = await create.mutateAsync({
        title,
        server_name: serverName,
        collection: collection === UNSCOPED ? null : collection,
      });
      onClose();
      onCreated(created);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <Modal onClose={onClose} open={open} size="md" title="New MCP server">
      <form className="space-y-4" onSubmit={submit}>
        <Input
          autoFocus
          description="Shown in Studio; also the suggested Name in Claude."
          label="Title"
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Product docs"
          required
          value={title}
        />
        <Input
          description="mcpServers key in the client config. Lowercase, alphanumeric + dashes."
          label="Server name"
          onChange={(e) => {
            setAutoSlug(false);
            setServerName(slugify(e.target.value));
          }}
          placeholder="bigrag-product-docs"
          required
          value={serverName}
        />
        <Select
          label="Collection scope"
          onChange={setCollection}
          options={[
            { value: UNSCOPED, label: "All collections (full workspace)" },
            ...collections.map((c) => ({ value: c.name, label: c.name })),
          ]}
          value={collection}
        />
        <p className="text-xs text-muted-foreground">
          Creating this MCP mints a fresh bigRAG API key scoped to it. The full URL (with key) is
          shown once — copy it into your MCP client immediately. You can rotate the key any time.
        </p>
        <div className="flex justify-end gap-2 pt-1">
          <Button onClick={onClose} type="button" variant="secondary">
            Cancel
          </Button>
          <Button disabled={create.isPending} type="submit">
            {create.isPending ? "Creating…" : "Create MCP"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};

interface CredentialDialogProps {
  open: boolean;
  onClose: () => void;
  created: CreatedMcpServer | null;
  kind: "created" | "rotated";
}

const CredentialDialog = ({ open, onClose, created, kind }: CredentialDialogProps) => {
  if (!created) return null;
  const origin = getOrigin();
  const remoteUrl = buildRemoteUrl(origin, created.api_key);
  const jsonSnippet = buildClaudeDesktopJson(created, origin, created.api_key);
  const shellSnippet = buildShellSnippet(origin, created.api_key);
  const isScoped = !!created.collection;

  return (
    <Modal
      footer={<Button onClick={onClose}>I&apos;ve saved the URL</Button>}
      onClose={onClose}
      open={open}
      size="xl"
      title={
        kind === "created" ? `MCP created — ${created.title}` : `MCP key rotated — ${created.title}`
      }
    >
      <div className="space-y-6">
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm">
          <div className="flex items-center gap-2 font-medium">
            <KeyRound className="size-4" /> This is the only time the full URL / key is shown.
          </div>
          <p className="mt-1 text-muted-foreground">
            Copy what you need now. If you lose it, rotate to mint a new one — the previous token
            stops working immediately.
          </p>
        </div>

        <section>
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="font-medium text-sm">Remote URL</h3>
            <span className="text-xs text-muted-foreground">
              Claude custom connector · remote Cursor
            </span>
          </div>
          <CodeBlock code={remoteUrl} label="remote MCP URL" />
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
            <li>
              In Claude, open <em>Add custom connector</em>.
            </li>
            <li>
              Set <em>Name</em> to{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono">{created.title}</code>.
            </li>
            <li>
              Paste the URL above into <em>Remote MCP server URL</em>.
            </li>
            <li>Leave the OAuth fields blank — auth is via the token query param.</li>
          </ol>
        </section>

        <section>
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="font-medium text-sm">Claude Desktop</h3>
            <span className="text-xs text-muted-foreground">Local stdio · config.json</span>
          </div>
          <CodeBlock code={jsonSnippet} label="Claude Desktop JSON config" />
        </section>

        <section>
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="font-medium text-sm">Shell (quick test)</h3>
            <span className="text-xs text-muted-foreground">stdio · foreground</span>
          </div>
          <CodeBlock code={shellSnippet} label="shell command" />
        </section>

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
      </div>
    </Modal>
  );
};

interface DetailDialogProps {
  open: boolean;
  onClose: () => void;
  server: McpServer | null;
  onRotate: () => void;
  rotating: boolean;
}

const DetailDialog = ({ open, onClose, server, onRotate, rotating }: DetailDialogProps) => {
  if (!server) return null;
  const origin = getOrigin();
  const redacted = `bigrag_sk_${server.key_prefix.replace(/^bigrag_sk_/, "")}…<REDACTED>`;
  const remoteUrl = buildRemoteUrl(origin, redacted);
  const jsonSnippet = buildClaudeDesktopJson(server, origin, redacted);
  const shellSnippet = buildShellSnippet(origin, redacted);
  const isScoped = !!server.collection;

  return (
    <Modal onClose={onClose} open={open} size="xl" title={`MCP — ${server.title}`}>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-muted-foreground">Server name</span>
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
            {server.server_name}
          </code>
          <span className="text-muted-foreground">· Scope</span>
          {isScoped ? (
            <Badge variant="neutral">pinned to {server.collection}</Badge>
          ) : (
            <Badge variant="neutral">all collections</Badge>
          )}
          <span className="text-muted-foreground">· Key</span>
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
            {server.key_prefix}…
          </code>
          <span className="ml-auto text-xs text-muted-foreground">
            Last used {server.last_used_at ? formatRelative(server.last_used_at) : "never"}
          </span>
        </div>

        <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
          <div className="font-medium">The full key is no longer available.</div>
          <p className="mt-1 text-muted-foreground">
            bigRAG only shows each key&apos;s full value at creation time. The snippets below use a
            placeholder where the token goes. To get a fresh, usable URL, rotate the key — the
            previous one will stop working.
          </p>
          <div className="mt-3">
            <Button disabled={rotating} onClick={onRotate} size="sm" variant="secondary">
              <RotateCcw className="size-4" /> {rotating ? "Rotating…" : "Rotate key"}
            </Button>
          </div>
        </div>

        <section>
          <h3 className="mb-2 font-medium text-sm">Remote URL (template)</h3>
          <CodeBlock code={remoteUrl} label="remote MCP URL template" />
        </section>

        <section>
          <h3 className="mb-2 font-medium text-sm">Claude Desktop (template)</h3>
          <CodeBlock code={jsonSnippet} label="Claude Desktop JSON template" />
        </section>

        <section>
          <h3 className="mb-2 font-medium text-sm">Shell (template)</h3>
          <CodeBlock code={shellSnippet} label="shell command template" />
        </section>

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
      </div>
    </Modal>
  );
};

const McpPage = () => {
  const { data, isPending } = useMcpServers();
  const { data: collectionsData } = useCollections();
  const rotate = useRotateMcpServer();
  const remove = useDeleteMcpServer();

  const servers = data?.servers ?? [];
  const collections = collectionsData?.collections ?? [];

  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [deleteFor, setDeleteFor] = useState<McpServer | null>(null);
  const [credential, setCredential] = useState<{
    server: CreatedMcpServer;
    kind: "created" | "rotated";
  } | null>(null);

  useEffect(() => {
    if (!credential) return;
    const timer = setTimeout(() => setCredential(null), 5 * 60 * 1000);
    return () => clearTimeout(timer);
  }, [credential]);

  const handleRotate = async () => {
    if (!detailId) return;
    try {
      const created = await rotate.mutateAsync(detailId);
      setDetailId(null);
      setCredential({ server: created, kind: "rotated" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to rotate");
    }
  };

  const confirmDelete = async () => {
    if (!deleteFor) return;
    try {
      await remove.mutateAsync(deleteFor.id);
      setDeleteFor(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const detailServer = servers.find((s) => s.id === detailId) ?? null;

  const columns: Column<McpServer>[] = [
    {
      header: "Title",
      key: "title",
      render: (s) => (
        <button
          className="flex items-center gap-2 text-left font-medium text-sm hover:underline"
          onClick={() => setDetailId(s.id)}
          type="button"
        >
          <Plug className="size-4 shrink-0 text-muted-foreground" /> {s.title}
        </button>
      ),
    },
    {
      header: "Server name",
      key: "server_name",
      className: "font-mono text-xs text-muted-foreground",
      render: (s) => s.server_name,
    },
    {
      header: "Scope",
      key: "scope",
      render: (s) =>
        s.collection ? (
          <Badge variant="neutral">{s.collection}</Badge>
        ) : (
          <span className="text-muted-foreground text-xs">all collections</span>
        ),
    },
    {
      header: "Key prefix",
      key: "key_prefix",
      className: "font-mono text-xs text-muted-foreground",
      render: (s) => `${s.key_prefix}…`,
    },
    {
      header: "Last used",
      key: "last_used_at",
      className: "text-muted-foreground",
      render: (s) => (s.last_used_at ? formatRelative(s.last_used_at) : "never"),
    },
    {
      header: "Actions",
      headerClassName: "text-right",
      className: "text-right",
      key: "actions",
      render: (s) => (
        <div className="flex items-center justify-end gap-2">
          <Tooltip content="Delete">
            <Button
              aria-label="Delete"
              className="hover:bg-destructive/10 hover:text-destructive"
              onClick={() => setDeleteFor(s)}
              size="sm"
              variant="ghost"
            >
              <Trash2 className="size-4" />
            </Button>
          </Tooltip>
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        actions={
          <div className="flex items-center gap-2">
            <a
              className="inline-flex h-9 items-center gap-2 rounded-full border border-border bg-background px-4 text-sm font-semibold text-foreground transition-colors hover:bg-accent"
              href="https://modelcontextprotocol.io"
              rel="noopener noreferrer"
              target="_blank"
            >
              <ExternalLink className="size-4" /> What is MCP?
            </a>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="size-4" /> New MCP
            </Button>
          </div>
        }
        description="Mint scoped MCP URLs for Claude Desktop, custom connectors, and any MCP client."
        title="MCP"
      />

      <DataTable
        columns={columns}
        data={servers}
        emptyAction={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" /> Create your first MCP
          </Button>
        }
        emptyDescription="Creating an MCP mints a bigRAG API key scoped to it and renders the full URL you can paste straight into Claude's connector."
        emptyIcon={<Plug className="size-6" />}
        emptyTitle="No MCP servers yet"
        keyExtractor={(s) => s.id}
        loading={isPending}
        loadingMessage="Loading MCP servers…"
      />

      <CreateDialog
        collections={collections.map((c) => ({ name: c.name }))}
        onClose={() => setCreateOpen(false)}
        onCreated={(created) => setCredential({ server: created, kind: "created" })}
        open={createOpen}
      />

      <CredentialDialog
        created={credential?.server ?? null}
        kind={credential?.kind ?? "created"}
        onClose={() => setCredential(null)}
        open={!!credential}
      />

      <DetailDialog
        onClose={() => setDetailId(null)}
        onRotate={handleRotate}
        open={!!detailServer}
        rotating={rotate.isPending}
        server={detailServer}
      />

      <ConfirmDialog
        confirmLabel="Delete"
        description={
          deleteFor
            ? `Delete MCP server "${deleteFor.title}"? Its URL stops working immediately.`
            : ""
        }
        loading={remove.isPending}
        onClose={() => setDeleteFor(null)}
        onConfirm={confirmDelete}
        open={!!deleteFor}
        title="Delete MCP server"
      />
    </div>
  );
};

export default McpPage;
