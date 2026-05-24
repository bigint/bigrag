import { useForm, useStore } from "@tanstack/react-form";
import { ExternalLink, KeyRound, Plug, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CopyButton } from "@/components/ui/copy-button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Page } from "@/components/ui/page";
import { Select } from "@/components/ui/select";
import { Tooltip } from "@/components/ui/tooltip";
import { bigragApiUrl } from "@/config/runtime";
import {
  defaultMcpCreateFormValues,
  MCP_UNSCOPED,
  mcpCreateBodyFromValues,
  mcpServerNameFromTitle,
  slugifyMcpServerName,
} from "@/features/mcp/mcp-form-state";
import { useCollections } from "@/hooks/use-collections";
import {
  useCreateMcpServer,
  useDeleteMcpServer,
  useMcpServers,
  useRotateMcpServer,
} from "@/hooks/use-mcp-servers";
import { errorText, submitWith } from "@/lib/form";
import { formatRelative } from "@/lib/format";
import type { CreatedMcpServer, McpServer } from "@/types/bigrag";

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

const trimSlash = (s: string) => s.replace(/\/+$/, "");

const buildRemoteUrl = (origin: string) => `${trimSlash(origin)}/mcp`;

const buildAuthHeader = (plaintext: string) => `Authorization: Bearer ${plaintext}`;

const buildClaudeDesktopJson = (serverName: string, origin: string, plaintext: string) =>
  JSON.stringify(
    {
      mcpServers: {
        [serverName]: {
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

const buildSnippets = (serverName: string, keyValue: string) => ({
  remoteUrl: buildRemoteUrl(bigragApiUrl),
  authHeader: buildAuthHeader(keyValue),
  jsonSnippet: buildClaudeDesktopJson(serverName, bigragApiUrl, keyValue),
  shellSnippet: buildShellSnippet(bigragApiUrl, keyValue),
});

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

const ToolsExposed = ({ isScoped }: { isScoped: boolean }) => (
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

interface CreateDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (created: CreatedMcpServer) => void;
  collections: { name: string }[];
}

type CredentialNotice = {
  server: CreatedMcpServer;
  kind: "created" | "rotated";
};

const CreateDialog = ({ open, onClose, onCreated, collections }: CreateDialogProps) => {
  const create = useCreateMcpServer();
  const [autoSlug, setAutoSlug] = useState(true);
  const form = useForm({
    defaultValues: defaultMcpCreateFormValues(),
    onSubmit: async ({ value }) => {
      try {
        const created = await create.mutateAsync(mcpCreateBodyFromValues(value));
        onClose();
        onCreated(created);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed");
      }
    },
  });
  const values = useStore(form.store, (state) => state.values);

  useEffect(() => {
    if (!open) {
      form.reset(defaultMcpCreateFormValues());
      setAutoSlug(true);
    }
  }, [form, open]);

  useEffect(() => {
    if (autoSlug) form.setFieldValue("serverName", mcpServerNameFromTitle(values.title));
  }, [autoSlug, form, values.title]);

  return (
    <Modal onClose={onClose} open={open} size="md" title="New MCP server">
      <form className="space-y-4" noValidate onSubmit={submitWith(() => form.handleSubmit())}>
        <form.Field
          name="title"
          validators={{
            onSubmit: ({ value }) => (value.trim() ? undefined : "Title is required"),
          }}
        >
          {(field) => (
            <Input
              autoFocus
              description="Shown in the admin UI; also the suggested Name in Claude."
              error={errorText(field.state.meta.errors)}
              label="Title"
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
              placeholder="Product docs"
              required
              value={field.state.value}
            />
          )}
        </form.Field>
        <form.Field
          name="serverName"
          validators={{
            onSubmit: ({ value }) => (value.trim() ? undefined : "Server name is required"),
          }}
        >
          {(field) => (
            <Input
              description="mcpServers key in the client config. Lowercase, alphanumeric + dashes."
              error={errorText(field.state.meta.errors)}
              label="Server name"
              onBlur={field.handleBlur}
              onChange={(e) => {
                setAutoSlug(false);
                field.handleChange(slugifyMcpServerName(e.target.value));
              }}
              placeholder="bigrag-product-docs"
              required
              value={field.state.value}
            />
          )}
        </form.Field>
        <form.Field name="collection">
          {(field) => (
            <Select
              label="Collection scope"
              onChange={field.handleChange}
              options={[
                { value: MCP_UNSCOPED, label: "All collections (full workspace)" },
                ...collections.map((c) => ({ value: c.name, label: c.name })),
              ]}
              value={field.state.value}
            />
          )}
        </form.Field>
        <p className="text-xs text-muted-foreground">
          Creating this MCP mints a fresh bigRAG API key scoped to it. The full key is shown once —
          copy it into your MCP client immediately. You can rotate the key any time.
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
  const [testing, setTesting] = useState(false);
  if (!created) return null;
  const { remoteUrl, authHeader, jsonSnippet, shellSnippet } = buildSnippets(
    created.server_name,
    created.api_key,
  );
  const isScoped = !!created.collection;
  const testCredential = async () => {
    setTesting(true);
    try {
      const response = await fetch(`${bigragApiUrl}/v1/auth/whoami`, {
        headers: { Authorization: `Bearer ${created.api_key}` },
      });
      if (!response.ok) throw new Error(await response.text());
      toast.success("MCP key connected");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "MCP key test failed");
    } finally {
      setTesting(false);
    }
  };

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
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 font-medium">
              <KeyRound className="size-4" /> This is the only time the full key is shown.
            </div>
            <Button disabled={testing} onClick={testCredential} size="sm" variant="secondary">
              {testing ? "Testing…" : "Test key"}
            </Button>
          </div>
          <p className="mt-1 text-muted-foreground">
            Copy what you need now. If you lose it, rotate to mint a new one — the previous key
            stops working immediately.
          </p>
        </div>

        <section>
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="font-medium text-sm">Remote HTTP</h3>
            <span className="text-xs text-muted-foreground">
              Clients that can send bearer headers
            </span>
          </div>
          <CodeBlock code={remoteUrl} label="remote MCP URL" />
          <div className="mt-3">
            <CodeBlock code={authHeader} label="remote MCP authorization header" />
          </div>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
            <li>Set the remote MCP server URL to the endpoint above.</li>
            <li>Send the bearer header above with every request.</li>
            <li>If your remote client cannot send headers, use the local stdio config below.</li>
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

        <ToolsExposed isScoped={isScoped} />
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
  const redacted = `bigrag_sk_${server.key_prefix.replace(/^bigrag_sk_/, "")}…<REDACTED>`;
  const { remoteUrl, authHeader, jsonSnippet, shellSnippet } = buildSnippets(
    server.server_name,
    redacted,
  );
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
            placeholder where the key goes. To get a fresh, usable key, rotate it — the previous one
            will stop working.
          </p>
          <div className="mt-3">
            <Button disabled={rotating} onClick={onRotate} size="sm" variant="secondary">
              <RotateCcw className="size-4" /> {rotating ? "Rotating…" : "Rotate key"}
            </Button>
          </div>
        </div>

        <section>
          <h3 className="mb-2 font-medium text-sm">Remote HTTP (template)</h3>
          <CodeBlock code={remoteUrl} label="remote MCP URL template" />
          <div className="mt-3">
            <CodeBlock code={authHeader} label="remote MCP authorization header template" />
          </div>
        </section>

        <section>
          <h3 className="mb-2 font-medium text-sm">Claude Desktop (template)</h3>
          <CodeBlock code={jsonSnippet} label="Claude Desktop JSON template" />
        </section>

        <section>
          <h3 className="mb-2 font-medium text-sm">Shell (template)</h3>
          <CodeBlock code={shellSnippet} label="shell command template" />
        </section>

        <ToolsExposed isScoped={isScoped} />
      </div>
    </Modal>
  );
};

export const McpPage = () => {
  const { data, error, isError, isPending, refetch } = useMcpServers();
  const { data: collectionsData } = useCollections();
  const rotate = useRotateMcpServer();
  const remove = useDeleteMcpServer();

  const servers = data?.servers ?? [];
  const collections = collectionsData?.collections ?? [];

  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [deleteFor, setDeleteFor] = useState<McpServer | null>(null);
  const [credential, setCredential] = useState<CredentialNotice | null>(null);

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
    <Page.Shell>
      <Page.Header
        actions={
          <div className="flex items-center gap-2">
            <a
              className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-background px-4 text-sm font-semibold text-foreground hover:bg-accent"
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
        className="mb-0"
        description="Mint scoped MCP keys for Claude Desktop, remote MCP clients, and local runtimes."
        title="MCP"
      />

      <DataTable
        columns={columns}
        data={servers}
        error={isError ? error : null}
        errorAction={
          <Button onClick={() => refetch()} variant="secondary">
            Retry
          </Button>
        }
        errorTitle="MCP servers unavailable"
        emptyAction={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" /> Create your first MCP
          </Button>
        }
        emptyDescription="Creating an MCP mints a bigRAG API key scoped to it and renders the endpoint plus one-time key for MCP clients."
        emptyIcon={<Plug className="size-6" />}
        emptyTitle="No MCP servers yet"
        keyExtractor={(s) => s.id}
        loading={isPending}
        loadingMessage="Loading MCP servers…"
      />

      <CreateDialog
        collections={collections}
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
    </Page.Shell>
  );
};
