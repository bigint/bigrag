import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/backups")({
  component: lazyRouteComponent(() =>
    import("@/features/backups/backups-page").then((m) => ({ default: m.BackupsPage })),
  ),
});
