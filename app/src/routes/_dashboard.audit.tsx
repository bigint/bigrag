import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/audit")({
  component: lazyRouteComponent(() =>
    import("@/features/audit/audit-page").then((m) => ({ default: m.AuditPage })),
  ),
});
