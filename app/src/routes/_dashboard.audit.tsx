import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense } from "react";
import { Spinner } from "@/components/ui/spinner";

const AuditPage = lazy(async () => ({
  default: (await import("@/features/audit/audit-page")).AuditPage,
}));

const AuditRoute = () => (
  <Suspense
    fallback={
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    }
  >
    <AuditPage />
  </Suspense>
);

export const Route = createFileRoute("/_dashboard/audit")({
  component: AuditRoute,
});
