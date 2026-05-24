export const MCP_UNSCOPED = "__all__";

export type McpCreateFormValues = {
  collection: string;
  serverName: string;
  title: string;
};

export const defaultMcpCreateFormValues = (): McpCreateFormValues => ({
  collection: MCP_UNSCOPED,
  serverName: "",
  title: "",
});

export const slugifyMcpServerName = (value: string) =>
  value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);

export const mcpServerNameFromTitle = (title: string) => slugifyMcpServerName(title) || "bigrag";

export const mcpCreateBodyFromValues = ({
  collection,
  serverName,
  title,
}: McpCreateFormValues) => ({
  collection: collection === MCP_UNSCOPED ? null : collection,
  server_name: serverName,
  title,
});
