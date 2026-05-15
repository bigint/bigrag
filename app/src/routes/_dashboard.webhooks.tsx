import { createFileRoute } from "@tanstack/react-router";
import { WebhooksPage } from "@/features/webhooks/webhooks-page";

export const Route = createFileRoute("/_dashboard/webhooks")({
  component: WebhooksPage,
});
