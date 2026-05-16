import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense } from "react";
import { Spinner } from "@/components/ui/spinner";

const OverviewPage = lazy(async () => ({
  default: (await import("@/features/overview/overview-page")).OverviewPage,
}));

const OverviewRoute = () => (
  <Suspense
    fallback={
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    }
  >
    <OverviewPage />
  </Suspense>
);

export const Route = createFileRoute("/_dashboard/overview")({
  component: OverviewRoute,
});
