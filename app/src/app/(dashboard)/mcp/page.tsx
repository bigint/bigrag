"use client";

import {
  Check,
  ChevronDown,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  Plug,
  Plus,
  Terminal,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select, type SelectOption } from "@/components/ui/select";
import { Tooltip } from "@/components/ui/tooltip";
import { useApiKeys } from "@/hooks/use-api-keys";
import { cn } from "@/lib/cn";
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

interface PersistedConfig extends McpConfig {}

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

const defaultConfig = (url: string): McpConfig => ({
  id: makeId(),
  title: "bigRAG",
  serverName: "bigrag",
  url,
  selectedKeyId: "",
});

const buildJsonSnippet = (c: McpConfig, apiKey: string) => {
  const env: Record<string, string> = {
    BIGRAG_URL: c.url.trim() || "http://localhost:6100",
    BIGRAG_API_KEY: apiKey.trim() || PLACEHOLDER_KEY,
  };
  return JSON.stringify(
    { mcpServers: { [c.serverName || "bigrag"]: { command: "bigrag-mcp", env } } },
    null,
    2,
  );
};

const buildShellSnippet = (c: McpConfig, apiKey: string) => {
  const lines = [
    `BIGRAG_URL=${c.url.trim() || "http://localhost:6100"}`,
    `BIGRAG_API_KEY=${apiKey.trim() || PLACEHOLDER_KEY}`,
  ];
  return `${lines.join(" \\\n  ")} \\\n  bigrag-mcp`;
};

const buildRemoteUrl = (c: McpConfig, apiKey: string) => {
  const base = (c.url.trim() || "http://localhost:6100").replace(/\/+$/, "");
  const token = apiKey.trim() || PLACEHOLDER_KEY;
  return `${base}/mcp?token=${encodeURIComponent(token)}`;
};

const CodeBlock = ({ code, label }: { code: string; label: string }) => {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    toast.success("Copied");
    setTimeout(() => setCopied(false), 1800);
  };
  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded-md border border-border bg-muted/50 p-4 font-mono text-xs leading-relaxed">
        <code>{code}</code>
      </pre>
      <div className="absolute top-2 right-2">
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
      </div>
    </div>
  );
};

interface ConfigCardProps {
  config: McpConfig;
  apiKey: string;
  onUpdate: (patch: Partial<McpConfig>) => void;
  onUpdateKey: (value: string) => void;
  onDelete: () => void;
  keyOptions: SelectOption[];
  hasActiveKeys: boolean;
  selectedKey: ApiKey | undefined;
}

const ConfigCard = ({
  config,
  apiKey,
  onUpdate,
  onUpdateKey,
  onDelete,
  keyOptions,
  hasActiveKeys,
  selectedKey,
}: ConfigCardProps) => {
  const [revealed, setRevealed] = useState(false);
  const [showShell, setShowShell] = useState(false);

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <CardTitle className="flex items-center gap-2">
            <Plug className="size-4 shrink-0 text-muted-foreground" />
            <span className="truncate">{config.title || "Untitled"}</span>
            {selectedKey?.collection ? (
              <Badge variant="neutral">{selectedKey.collection}</Badge>
            ) : selectedKey ? (
              <Badge variant="neutral">all collections</Badge>
            ) : null}
          </CardTitle>
          <CardDescription className="mt-1">
            Server name{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
              {config.serverName || "bigrag"}
            </code>
            {selectedKey?.collection
              ? ` — auto-scoped to collection "${selectedKey.collection}" (derived from the key)`
              : selectedKey
                ? " — full-workspace access"
                : ""}
          </CardDescription>
        </div>
        <Tooltip content="Delete configuration">
          <Button
            aria-label="Delete configuration"
            className="hover:bg-destructive/10 hover:text-destructive"
            onClick={onDelete}
            size="sm"
            variant="ghost"
          >
            <Trash2 className="size-4" />
          </Button>
        </Tooltip>
      </CardHeader>

      <CardContent className="space-y-4">
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
                No active keys.{" "}
                <Link className="font-medium text-primary underline" href="/api-keys">
                  Create one
                </Link>
                .
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

        <div className="space-y-2">
          <div className="flex items-baseline justify-between">
            <div className="text-xs font-medium text-muted-foreground">
              Remote URL (Claude custom connector, remote Cursor)
            </div>
            <div className="text-xs text-muted-foreground">
              Paste as <em>Remote MCP server URL</em>.
            </div>
          </div>
          <CodeBlock code={buildRemoteUrl(config, apiKey)} label="remote MCP URL" />
          <p className="text-xs text-muted-foreground">
            The token is embedded as a URL query param. Treat the URL like a password — it may
            appear in reverse-proxy / server logs. Revoke the key if the URL leaks.
          </p>
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium text-muted-foreground">
            Local stdio (Claude Desktop <code className="font-mono">config.json</code>, legacy
            Cursor)
          </div>
          <CodeBlock code={buildJsonSnippet(config, apiKey)} label="JSON config" />
        </div>

        <button
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setShowShell((v) => !v)}
          type="button"
        >
          <Terminal className="size-3.5" />
          {showShell ? "Hide" : "Show"} shell command
          <ChevronDown className={cn("size-3.5 transition-transform", showShell && "rotate-180")} />
        </button>
        {showShell && <CodeBlock code={buildShellSnippet(config, apiKey)} label="shell command" />}
      </CardContent>
    </Card>
  );
};

const McpPage = () => {
  const { data: keysData, isPending: keysPending } = useApiKeys();
  const activeKeys = useMemo(() => (keysData?.keys ?? []).filter((k) => k.active), [keysData]);

  const [configs, setConfigs] = useState<McpConfig[]>([]);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const origin = window.location.origin;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as PersistedConfig[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          setConfigs(parsed);
          setHydrated(true);
          return;
        }
      }
    } catch {
      // malformed storage — fall through to default
    }
    setConfigs([defaultConfig(origin)]);
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
    setConfigs((prev) => {
      const count = prev.length + 1;
      return [
        ...prev,
        { ...defaultConfig(origin), title: `bigRAG ${count}`, serverName: `bigrag-${count}` },
      ];
    });
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

  const scoped = configs.some((c) => {
    const k = activeKeys.find((ak) => ak.id === c.selectedKeyId);
    return !!k?.collection;
  });
  const unscoped = configs.some((c) => {
    const k = activeKeys.find((ak) => ak.id === c.selectedKeyId);
    return k && !k.collection;
  });

  return (
    <div className="space-y-6">
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
              <Plus className="size-4" /> New configuration
            </Button>
          </div>
        }
        description="Generate Claude Desktop, Cursor, and shell configs. Scope comes from the API key — pick a collection-scoped key to limit the MCP server to that collection."
        title="MCP"
      />

      {!hydrated ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Loading…
          </CardContent>
        </Card>
      ) : configs.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <Plug className="size-8 text-muted-foreground" />
            <div className="font-medium">No configurations</div>
            <div className="max-w-md text-sm text-muted-foreground">
              Create one for each MCP client you want to connect.
            </div>
            <Button onClick={addConfig}>
              <Plus className="size-4" /> New configuration
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {configs.map((c) => (
            <ConfigCard
              apiKey={apiKeys[c.id] ?? ""}
              config={c}
              hasActiveKeys={!keysPending && activeKeys.length > 0}
              key={c.id}
              keyOptions={keyOptions}
              onDelete={() => setDeleteId(c.id)}
              onUpdate={(patch) => updateConfig(c.id, patch)}
              onUpdateKey={(v) => setApiKeyFor(c.id, v)}
              selectedKey={activeKeys.find((k) => k.id === c.selectedKeyId)}
            />
          ))}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Tools exposed</CardTitle>
          <CardDescription>
            Read-only retrieval tools. Ingestion and writes aren&apos;t exposed — use the API or
            Studio for those.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {unscoped && (
            <div>
              <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Unscoped key → full tool set
              </div>
              <ul className="divide-y divide-border">
                {TOOLS_UNSCOPED.map((tool) => (
                  <li
                    className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0"
                    key={tool.name}
                  >
                    <code className="mt-0.5 shrink-0 font-mono text-sm">{tool.name}</code>
                    <span className="text-sm text-muted-foreground">{tool.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {scoped && (
            <div>
              <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Collection-scoped key → scoped tool set
              </div>
              <ul className="divide-y divide-border">
                {TOOLS_SCOPED.map((tool) => (
                  <li
                    className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0"
                    key={tool.name}
                  >
                    <code className="mt-0.5 shrink-0 font-mono text-sm">{tool.name}</code>
                    <span className="text-sm text-muted-foreground">{tool.description}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-muted-foreground">
                Scoped servers drop the <code className="font-mono">collection</code> argument and
                hide <code className="font-mono">list_collections</code> /{" "}
                <code className="font-mono">multi_collection_query</code>.
              </p>
            </div>
          )}
          {!scoped && !unscoped && (
            <p className="text-sm text-muted-foreground">
              Select an API key on a configuration to see which tools that server will expose.
            </p>
          )}
        </CardContent>
      </Card>

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
