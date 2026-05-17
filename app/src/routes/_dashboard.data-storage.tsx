import { createFileRoute } from "@tanstack/react-router";
import { DataStoragePage } from "@/features/data-storage/data-storage-page";

export const Route = createFileRoute("/_dashboard/data-storage")({
  component: () => <DataStoragePage />,
});
