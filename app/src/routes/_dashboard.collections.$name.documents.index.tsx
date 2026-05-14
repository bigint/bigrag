import { createFileRoute } from "@tanstack/react-router";
import { DocumentsTab } from "@/features/collections/documents-tab";

const DocumentsRoute = () => {
  const { name: rawName } = Route.useParams();
  return <DocumentsTab name={decodeURIComponent(rawName)} />;
};

export const Route = createFileRoute("/_dashboard/collections/$name/documents/")({
  component: DocumentsRoute,
});
