import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/usage")({
  component: lazyRouteComponent(() =>
    import("@/features/usage/usage-page").then((m) => ({ default: m.UsagePage })),
  ),
});
