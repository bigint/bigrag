"use client";

import { Check, Copy, ExternalLink, Eye, EyeOff, Pencil, Plug, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { Select, type SelectOption } from "@/components/ui/select";
import { Tooltip } from "@/components/ui/tooltip";
import { useApiKeys } from "@/hooks/use-api-keys";
import type { ApiKey } from "@/types/bigrag";

const STORAGE_KEY = "bigrag:mcp:configs:v2";
const PLACEHOLDER_KEY = "bigrag_sk_YOUR_API_KEY";

interface McpConfig {
  id: string;
  title: string;
  serverName: string;
  url: string;
  selectedKeyId: string;
}

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
    .slice(0, 32);

const makeId = () => `cfg_${Math.random().toString(36).slice(2, 10)}`;

const defaultConfig = (url: string, index: number): McpConfig => ({
  id: makeId(),
  title: index === 0 ? "bigRAG" : `bigRAG ${index + 1}`,
  serverName: index === 0 ? "bigrag" : `bigrag-${index + 1}`,
  url,
  selectedKeyId: "",
});

const trimTrailingSlash = (s: string) => s.replace(/\/+$/, "");
const safeUrl = (url: string) => trimTrailingSlash(url.trim() || "http://localhost:6100");

const buildClaudeDesktopJson = (c: McpConfig, apiKey: string) =>
  JSON.stringify(
    {
      mcpServers: {
        [c.serverName || "bigrag"]: {
          command: "bigrag-mcp",
          env: {
            BIGRAG_URL: safeUrl(c.url),
            BIGRAG_API_KEY: apiKey.trim() || PLACEHOLDER_KEY,
          },
        },
      },
    },
    null,
    2,
  );

const buildShellSnippet = (c: McpConfig, apiKey: string) =>
  `BIGRAG_URL=${safeUrl(c.url)} \\
  BIGRAG_API_KEY=${apiKey.trim() || PLACEHOLDER_KEY} \\
  bigrag-mcp`;

const buildRemoteUrl = (c: McpConfig, apiKey: string) =>
  `${safeUrl(c.url)}/mcp?token=${encodeURIComponent(apiKey.trim() || PLACEHOLDER_KEY)}`;

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

interface ConfigDialogProps {
  open: boolean;
  onClose: () => void;
  config: McpConfig | null;
  apiKey: string;
  onUpdate: (patch: Partial<McpConfig>) => void;
  onUpdateKey: (value: string) => void;
  keyOptions: SelectOption[];
  hasActiveKeys: boolean;
  selectedKey: ApiKey | undefined;
  keysPending: boolean;
  mode: "create" | "edit";
}

const ConfigDialog = ({
  open,
  onClose,
  config,
  apiKey,
  onUpdate,
  onUpdateKey,
  keyOptions,
  hasActiveKeys,
  selectedKey,
  keysPending,
  mode,
}: ConfigDialogProps) => {
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (!open) setRevealed(false);
  }, [open]);

  if (!config) return null;

  const isScoped = Boolean(selectedKey?.collection);
  const hasKey = !!selectedKey;
  const remoteUrl = buildRemoteUrl(config, apiKey);
  const jsonSnippet = buildClaudeDesktopJson(config, apiKey);
  const shellSnippet = buildShellSnippet(config, apiKey);

  return (
    <Modal
      onClose={onClose}
      open={open}
      size="xl"
      title={mode === "create" ? "New MCP configuration" : `MCP — ${config.title || "Untitled"}`}
    >
      <div className="space-y-8">
        <section>
          <h3 className="mb-3 font-medium text-sm">Basics</h3>
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              autoComplete="off"
              description="Freeform label for your own reference."
              label="Title"
              onChange={(e) => onUpdate({ title: e.target.value })}
              placeholder="Product docs"
              value={config.title}
            />
            <Input
              autoComplete="off"
              description="Used as the mcpServers key in the client config."
              label="Server name"
              onChange={(e) => onUpdate({ serverName: slugify(e.target.value) })}
              placeholder="bigrag-product-docs"
              value={config.serverName}
            />
            <Input
              autoComplete="off"
              description="Public bigRAG URL. Usually this Studio's origin."
              label="URL"
              onChange={(e) => onUpdate({ url: e.target.value })}
              placeholder="http://localhost:6100"
              value={config.url}
            />
            {hasActiveKeys ? (
              <Select
                label="API key"
                onChange={(v) => onUpdate({ selectedKeyId: v })}
                options={keyOptions}
                value={config.selectedKeyId}
              />
            ) : (
              <div>
                <div className="mb-1 block text-sm font-medium">API key</div>
                <div className="rounded-md border border-dashed border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                  {keysPending ? (
                    "Loading keys…"
                  ) : (
                    <>
                      No active keys.{" "}
                      <Link className="font-medium text-primary underline" href="/api-keys">
                        Create one
                      </Link>
                      .
                    </>
                  )}
                </div>
              </div>
            )}
            <div className="md:col-span-2">
              <Input
                autoComplete="off"
                description={
                  selectedKey
                    ? `Paste the full value for key "${selectedKey.name}". Not stored anywhere.`
                    : "Paste the full key value. Not stored anywhere."
                }
                label="API key value"
                onChange={(e) => onUpdateKey(e.target.value)}
                placeholder={PLACEHOLDER_KEY}
                spellCheck={false}
                trailing={
                  <Tooltip content={revealed ? "Hide" : "Reveal"}>
                    <button
                      aria-label={revealed ? "Hide key" : "Reveal key"}
                      className="inline-flex size-7 items-center justify-center rounded-md hover:bg-accent"
                      onClick={() => setRevealed((v) => !v)}
                      type="button"
                    >
                      {revealed ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </Tooltip>
                }
                type={revealed ? "text" : "password"}
                value={apiKey}
              />
            </div>
          </div>
          {hasKey && (
            <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
              <span>Server scope:</span>
              {isScoped ? (
                <Badge variant="neutral">pinned to {selectedKey?.collection}</Badge>
              ) : (
                <Badge variant="neutral">all collections</Badge>
              )}
            </div>
          )}
        </section>

        <section>
          <div className="mb-3 flex items-baseline justify-between">
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
              <code className="rounded bg-muted px-1 py-0.5 font-mono">
                {config.title || "bigRAG"}
              </code>
              .
            </li>
            <li>
              Paste the URL above into <em>Remote MCP server URL</em>.
            </li>
            <li>
              Leave the OAuth fields blank — auth is via the{" "}
              <code className="font-mono">?token=</code> query param.
            </li>
          </ol>
          <p className="mt-2 text-xs text-muted-foreground">
            The token is embedded in the URL. Treat the URL like a password — it may appear in
            reverse-proxy / server logs. Revoke the key in{" "}
            <Link className="font-medium text-primary underline" href="/api-keys">
              API keys
            </Link>{" "}
            if the URL leaks.
          </p>
        </section>

        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h3 className="font-medium text-sm">Claude Desktop</h3>
            <span className="text-xs text-muted-foreground">Local stdio · config.json</span>
          </div>
          <CodeBlock code={jsonSnippet} label="Claude Desktop JSON config" />
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
            <li>
              Install the CLI:{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono">uv tool install bigrag</code>{" "}
              (or <code className="rounded bg-muted px-1 py-0.5 font-mono">pip install bigrag</code>
              ).
            </li>
            <li>
              Open{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono">
                ~/Library/Application Support/Claude/claude_desktop_config.json
              </code>{" "}
              (macOS) or{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono">
                %APPDATA%\Claude\claude_desktop_config.json
              </code>{" "}
              (Windows).
            </li>
            <li>Merge the snippet above into the existing file.</li>
            <li>
              Restart Claude Desktop. The{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono">
                {config.serverName || "bigrag"}
              </code>{" "}
              server appears under the tools icon.
            </li>
          </ol>
        </section>

        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h3 className="font-medium text-sm">Shell (quick test)</h3>
            <span className="text-xs text-muted-foreground">stdio · foreground</span>
          </div>
          <CodeBlock code={shellSnippet} label="shell command" />
          <p className="mt-2 text-xs text-muted-foreground">
            Runs the stdio server in your terminal. Ctrl-C to stop. Useful for verifying auth before
            wiring it into a client.
          </p>
        </section>

        <section>
          <h3 className="mb-3 font-medium text-sm">
            Tools exposed {hasKey ? (isScoped ? "(scoped set)" : "(full set)") : ""}
          </h3>
          {!hasKey ? (
            <p className="text-sm text-muted-foreground">
              Pick an API key above to see which tools this server will expose.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {(isScoped ? TOOLS_SCOPED : TOOLS_UNSCOPED).map((tool) => (
                <li className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0" key={tool.name}>
                  <code className="mt-0.5 shrink-0 font-mono text-sm">{tool.name}</code>
                  <span className="text-sm text-muted-foreground">{tool.description}</span>
                </li>
              ))}
            </ul>
          )}
          {isScoped && (
            <p className="mt-2 text-xs text-muted-foreground">
              Scoped servers drop the <code className="font-mono">collection</code> argument and
              hide <code className="font-mono">list_collections</code> /{" "}
              <code className="font-mono">multi_collection_query</code>.
            </p>
          )}
        </section>
      </div>
    </Modal>
  );
};

const McpPage = () => {
  const { data: keysData, isPending: keysPending } = useApiKeys();
  const activeKeys = useMemo(() => (keysData?.keys ?? []).filter((k) => k.active), [keysData]);

  const [configs, setConfigs] = useState<McpConfig[]>([]);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [openId, setOpenId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as McpConfig[];
        if (Array.isArray(parsed)) {
          setConfigs(parsed);
          setHydrated(true);
          return;
        }
      }
    } catch {
      // malformed storage — fall through to empty
    }
    setConfigs([]);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || typeof window === "undefined") return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(configs));
    } catch {
      // storage full or disabled — ignore
    }
  }, [configs, hydrated]);

  const keyOptions: SelectOption[] = useMemo(
    () =>
      activeKeys.map((k) => ({
        value: k.id,
        label: k.collection
          ? `${k.name} · ${k.prefix}… · ${k.collection}`
          : `${k.name} · ${k.prefix}…`,
      })),
    [activeKeys],
  );

  const addConfig = () => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const fresh = defaultConfig(origin, configs.length);
    setConfigs((prev) => [...prev, fresh]);
    setOpenId(fresh.id);
  };

  const updateConfig = (id: string, patch: Partial<McpConfig>) => {
    setConfigs((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)));
  };

  const setApiKeyFor = (id: string, value: string) => {
    setApiKeys((prev) => ({ ...prev, [id]: value }));
  };

  const confirmDelete = () => {
    if (!deleteId) return;
    setConfigs((prev) => prev.filter((c) => c.id !== deleteId));
    setApiKeys((prev) => {
      const next = { ...prev };
      delete next[deleteId];
      return next;
    });
    setDeleteId(null);
  };

  const openConfig = configs.find((c) => c.id === openId) ?? null;
  const openKey = openConfig
    ? activeKeys.find((k) => k.id === openConfig.selectedKeyId)
    : undefined;
  const openIsNew = openConfig ? !openConfig.selectedKeyId && !apiKeys[openConfig.id] : false;

  const columns: Column<McpConfig>[] = [
    {
      header: "Title",
      key: "title",
      render: (c) => (
        <button
          className="flex items-center gap-2 text-left font-medium text-sm hover:underline"
          onClick={() => setOpenId(c.id)}
          type="button"
        >
          <Plug className="size-4 shrink-0 text-muted-foreground" />
          {c.title || <span className="text-muted-foreground italic">Untitled</span>}
        </button>
      ),
    },
    {
      header: "Server name",
      key: "serverName",
      className: "font-mono text-xs text-muted-foreground",
      render: (c) => c.serverName || "—",
    },
    {
      header: "Key",
      key: "key",
      render: (c) => {
        const k = activeKeys.find((ak) => ak.id === c.selectedKeyId);
        if (!k) return <span className="text-muted-foreground text-xs">— not selected —</span>;
        return <span className="text-sm">{k.name}</span>;
      },
    },
    {
      header: "Scope",
      key: "scope",
      render: (c) => {
        const k = activeKeys.find((ak) => ak.id === c.selectedKeyId);
        if (!k) return <span className="text-muted-foreground text-xs">—</span>;
        return k.collection ? (
          <Badge variant="neutral">{k.collection}</Badge>
        ) : (
          <span className="text-muted-foreground text-xs">all collections</span>
        );
      },
    },
    {
      header: "Actions",
      headerClassName: "text-right",
      className: "text-right",
      key: "actions",
      render: (c) => (
        <div className="flex items-center justify-end gap-2">
          <Tooltip content="View config">
            <Button
              aria-label="View config"
              onClick={() => setOpenId(c.id)}
              size="sm"
              variant="ghost"
            >
              <Pencil className="size-4" />
            </Button>
          </Tooltip>
          <Tooltip content="Delete">
            <Button
              aria-label="Delete"
              className="hover:bg-destructive/10 hover:text-destructive"
              onClick={() => setDeleteId(c.id)}
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
              className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-background px-4 text-sm font-medium text-foreground transition-colors hover:bg-accent"
              href="https://modelcontextprotocol.io"
              rel="noopener noreferrer"
              target="_blank"
            >
              <ExternalLink className="size-4" /> What is MCP?
            </a>
            <Button onClick={addConfig}>
              <Plus className="size-4" /> New MCP
            </Button>
          </div>
        }
        description="Generate Claude custom connector, Claude Desktop, and shell configurations. Scope follows the API key you select."
        title="MCP"
      />

      <DataTable
        columns={columns}
        data={configs}
        emptyAction={
          <Button onClick={addConfig}>
            <Plus className="size-4" /> Create your first MCP
          </Button>
        }
        emptyDescription="Create one for each MCP client (Claude custom connector, Claude Desktop, Cursor). Scope follows the API key you pick."
        emptyIcon={<Plug className="size-6" />}
        emptyTitle={hydrated ? "No MCP configurations yet" : "Loading…"}
        keyExtractor={(c) => c.id}
        loading={!hydrated}
        loadingMessage="Loading configurations…"
      />

      <ConfigDialog
        apiKey={openConfig ? (apiKeys[openConfig.id] ?? "") : ""}
        config={openConfig}
        hasActiveKeys={!keysPending && activeKeys.length > 0}
        keyOptions={keyOptions}
        keysPending={keysPending}
        mode={openIsNew ? "create" : "edit"}
        onClose={() => setOpenId(null)}
        onUpdate={(patch) => openConfig && updateConfig(openConfig.id, patch)}
        onUpdateKey={(v) => openConfig && setApiKeyFor(openConfig.id, v)}
        open={!!openConfig}
        selectedKey={openKey}
      />

      <ConfirmDialog
        confirmLabel="Delete"
        description="Delete this MCP configuration? Your API key is not stored anywhere and will not be affected."
        onClose={() => setDeleteId(null)}
        onConfirm={confirmDelete}
        open={!!deleteId}
        title="Delete configuration"
      />
    </div>
  );
};

export default McpPage;
