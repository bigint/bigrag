import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense } from "react";
import { Spinner } from "@/components/ui/spinner";

type ConnectorsSearch = {
  google_error?: string;
};

const ConnectorsPage = lazy(async () => ({
  default: (await import("@/features/connectors/connectors-page")).ConnectorsPage,
}));

const ConnectorsRoute = () => (
  <Suspense
    fallback={
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    }
  >
    <ConnectorsPage />
  </Suspense>
);

export const Route = createFileRoute("/_dashboard/connectors")({
  validateSearch: (search: Record<string, unknown>): ConnectorsSearch => ({
    google_error: typeof search.google_error === "string" ? search.google_error : undefined,
  }),
  component: ConnectorsRoute,
});
