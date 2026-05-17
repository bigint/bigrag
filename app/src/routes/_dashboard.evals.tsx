import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/evals")({
  component: lazyRouteComponent(() =>
    import("@/features/evals/evals-page").then((m) => ({ default: m.EvalsPage })),
  ),
});
