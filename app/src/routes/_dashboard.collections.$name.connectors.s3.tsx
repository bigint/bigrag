import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/collections/$name/connectors/s3")({
  component: () =>
    import("@/features/collections/s3-connector-route").then((m) => ({
      default: m.S3Connector,
    })),
});
