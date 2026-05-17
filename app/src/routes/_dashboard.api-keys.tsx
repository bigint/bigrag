import { createFileRoute } from "@tanstack/react-router";
import { ApiKeysPage } from "@/features/api-keys/api-keys-page";

export const Route = createFileRoute("/_dashboard/api-keys")({
  component: () => <ApiKeysPage />,
});
