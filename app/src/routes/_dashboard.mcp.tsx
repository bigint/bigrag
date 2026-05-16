import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense } from "react";
import { Spinner } from "@/components/ui/spinner";

const McpPage = lazy(async () => ({
  default: (await import("@/features/mcp/mcp-page")).McpPage,
}));

const McpRoute = () => (
  <Suspense
    fallback={
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    }
  >
    <McpPage />
  </Suspense>
);

export const Route = createFileRoute("/_dashboard/mcp")({
  component: McpRoute,
});
