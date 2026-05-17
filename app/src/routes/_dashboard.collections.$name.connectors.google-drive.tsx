import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/collections/$name/connectors/google-drive")({
  component: lazyRouteComponent(() =>
    import("@/features/collections/google-drive-route").then((m) => ({
      default: m.GoogleDriveConnector,
    })),
  ),
});
