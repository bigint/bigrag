import { KeyRound, RotateCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { Modal } from "@/components/ui/modal";
import { buildSnippets } from "@/features/mcp/mcp-snippets";
import { ToolsExposed } from "@/features/mcp/tools-exposed";
import { useVerifyCredential } from "@/hooks/use-verify-credential";
import { formatRelativeOrNever } from "@/lib/format";

export type McpCredentialMode = "created" | "rotated" | "detail";

interface McpCredentialDialogProps {
  open: boolean;
  onClose: () => void;
  mode: McpCredentialMode;
  title: string;
  serverName: string;
  keyValue: string;
  isScoped: boolean;
  collection?: string | null;
  keyPrefix?: string;
  lastUsedAt?: string | null;
  onRotate?: () => void;
  rotating?: boolean;
}

export const McpCredentialDialog = ({
  open,
  onClose,
  mode,
  title,
  serverName,
  keyValue,
  isScoped,
  collection,
  keyPrefix,
  lastUsedAt,
  onRotate,
  rotating,
}: McpCredentialDialogProps) => {
  const { verifying: testing, verify } = useVerifyCredential();
  const { remoteUrl, authHeader, jsonSnippet, shellSnippet } = buildSnippets(serverName, keyValue);
  const isDetail = mode === "detail";

  const testCredential = () =>
    verify(keyValue, {
      successMessage: "MCP key connected",
      errorMessage: "MCP key test failed",
    });

  const modalTitle = isDetail
    ? `MCP — ${title}`
    : mode === "created"
      ? `MCP created — ${title}`
      : `MCP key rotated — ${title}`;

  return (
    <Modal
      footer={isDetail ? undefined : <Button onClick={onClose}>I&apos;ve saved the URL</Button>}
      onClose={onClose}
      open={open}
      size="xl"
      title={modalTitle}
    >
      <div className="space-y-6">
        {isDetail ? (
          <>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="text-muted-foreground">Server name</span>
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{serverName}</code>
              <span className="text-muted-foreground">· Scope</span>
              {isScoped ? (
                <Badge variant="neutral">pinned to {collection}</Badge>
              ) : (
                <Badge variant="neutral">all collections</Badge>
              )}
              <span className="text-muted-foreground">· Key</span>
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{keyPrefix}…</code>
              <span className="ml-auto text-xs text-muted-foreground">
                Last used {formatRelativeOrNever(lastUsedAt)}
              </span>
            </div>

            <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
              <div className="font-medium">The full key is no longer available.</div>
              <p className="mt-1 text-muted-foreground">
                bigRAG only shows each key&apos;s full value at creation time. The snippets below
                use a placeholder where the key goes. To get a fresh, usable key, rotate it — the
                previous one will stop working.
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
          </>
        ) : (
          <>
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
                <li>
                  If your remote client cannot send headers, use the local stdio config below.
                </li>
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
          </>
        )}

        <ToolsExposed isScoped={isScoped} />
      </div>
    </Modal>
  );
};
