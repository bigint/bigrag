import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/webhooks")({
  component: lazyRouteComponent(() =>
    import("@/features/webhooks/webhooks-page").then((m) => ({ default: m.WebhooksPage })),
  ),
});
