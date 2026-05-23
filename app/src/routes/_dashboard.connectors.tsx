import { createFileRoute } from "@tanstack/react-router";
import { ConnectorsPage } from "@/features/connectors/connectors-page";

export const Route = createFileRoute("/_dashboard/connectors")({
  component: () => <ConnectorsPage />,
});
