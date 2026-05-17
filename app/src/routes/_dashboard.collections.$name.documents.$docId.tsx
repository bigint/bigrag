import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/collections/$name/documents/$docId")({
  component: lazyRouteComponent(() =>
    import("@/features/collections/document-detail-route").then((m) => ({
      default: m.DocumentDetail,
    })),
  ),
});
