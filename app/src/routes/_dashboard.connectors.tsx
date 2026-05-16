import { createFileRoute } from "@tanstack/react-router";
import { ConnectorsPage } from "@/features/connectors/connectors-page";

type ConnectorsSearch = {
  google_error?: string;
};

export const Route = createFileRoute("/_dashboard/connectors")({
  validateSearch: (search: Record<string, unknown>): ConnectorsSearch => ({
    google_error: typeof search.google_error === "string" ? search.google_error : undefined,
  }),
  component: () => <ConnectorsPage />,
});
