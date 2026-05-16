import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense } from "react";
import { Spinner } from "@/components/ui/spinner";

const DocumentsTab = lazy(async () => ({
  default: (await import("@/features/collections/documents-tab")).DocumentsTab,
}));

const DocumentsRoute = () => {
  const { name: rawName } = Route.useParams();
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      }
    >
      <DocumentsTab name={decodeURIComponent(rawName)} />
    </Suspense>
  );
};

export const Route = createFileRoute("/_dashboard/collections/$name/documents/")({
  component: DocumentsRoute,
});
