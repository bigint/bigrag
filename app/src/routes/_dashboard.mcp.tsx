import { createFileRoute } from "@tanstack/react-router";
import { McpPage } from "@/features/mcp/mcp-page";

export const Route = createFileRoute("/_dashboard/mcp")({
  component: () => <McpPage />,
});
