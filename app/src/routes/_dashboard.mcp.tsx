import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/mcp")({
  component: lazyRouteComponent(() =>
    import("@/features/mcp/mcp-page").then((m) => ({ default: m.McpPage })),
  ),
});
