import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/access-logs")({
  component: lazyRouteComponent(() =>
    import("@/features/access-logs/access-logs-page").then((m) => ({
      default: m.AccessLogsPage,
    })),
  ),
});
