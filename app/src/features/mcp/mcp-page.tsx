import { ExternalLink, Plug, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DataTable } from "@/components/ui/data-table";
import { Page } from "@/components/ui/page";
import { mcpColumns } from "@/features/mcp/mcp-columns";
import { McpCreateDialog } from "@/features/mcp/mcp-create-dialog";
import { McpCredentialDialog } from "@/features/mcp/mcp-credential-dialog";
import { useCollections } from "@/hooks/use-collections";
import { useDeleteMcpServer, useMcpServers, useRotateMcpServer } from "@/hooks/use-mcp-servers";
import type { CreatedMcpServer, McpServer } from "@/types/bigrag";

type CredentialNotice = {
  server: CreatedMcpServer;
  kind: "created" | "rotated";
};

const redactedKey = (server: McpServer) =>
  `bigrag_sk_${server.key_prefix.replace(/^bigrag_sk_/, "")}…<REDACTED>`;

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
  const columns = mcpColumns({ onOpenDetail: setDetailId, onDelete: setDeleteFor });

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

      <McpCreateDialog
        collections={collections}
        onClose={() => setCreateOpen(false)}
        onCreated={(created) => setCredential({ server: created, kind: "created" })}
        open={createOpen}
      />

      {credential && (
        <McpCredentialDialog
          open={!!credential}
          onClose={() => setCredential(null)}
          mode={credential.kind}
          title={credential.server.title}
          serverName={credential.server.server_name}
          keyValue={credential.server.api_key}
          isScoped={!!credential.server.collection}
        />
      )}

      {detailServer && (
        <McpCredentialDialog
          open={!!detailServer}
          onClose={() => setDetailId(null)}
          mode="detail"
          title={detailServer.title}
          serverName={detailServer.server_name}
          keyValue={redactedKey(detailServer)}
          isScoped={!!detailServer.collection}
          collection={detailServer.collection}
          keyPrefix={detailServer.key_prefix}
          lastUsedAt={detailServer.last_used_at}
          onRotate={handleRotate}
          rotating={rotate.isPending}
        />
      )}

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
