import { createFileRoute } from "@tanstack/react-router";
import { VectorStoragePage } from "@/features/vector-storage/vector-storage-page";

export const Route = createFileRoute("/_dashboard/vector-storage")({
  component: () => <VectorStoragePage />,
});
